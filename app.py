from flask import Flask, render_template, request, flash, redirect, jsonify, url_for, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import os
import sys
import signal
import atexit
import threading
import logging
import json
import re
import hmac
import hashlib
import base64
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs, quote

from utils.personalize import personalize
from utils.whatsapp import send_text, get_templates, send_template, upload_media, upload_media_from_bytes
from utils.logger import log_message, setup_logging
from utils.rate_limiter import RateLimiter, MessageQueue
from utils.background_scheduler import schedule_message_job, get_scheduled_jobs, cancel_job
from utils.auth import UserManager
from utils.database import Database
from utils.flow_engine import (
    start_flow_engine, enroll_participant as flow_enroll_participant,
    trigger_immediate_recheck, get_flow_first_step_key, build_trigger_context
)

setup_logging()
logger = logging.getLogger(__name__)

# Validate required environment variables
required_env_vars = ['WHATSAPP_ACCESS_TOKEN', 'WHATSAPP_PHONE_NUMBER_ID', 'WABA_ID', 'SECRET_KEY']
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"❌ Missing required environment variables: {', '.join(missing_vars)}\nPlease configure them in your .env file")

# Load from environment variables
WABA_ID = os.getenv('WABA_ID')
SECRET_KEY = os.getenv('SECRET_KEY')

# Rate limiting configuration
MAX_REQUESTS = int(os.getenv('RATE_LIMIT_REQUESTS', '20'))
TIME_WINDOW = float(os.getenv('RATE_LIMIT_WINDOW', '1.0'))
NUM_WORKERS = int(os.getenv('MESSAGE_QUEUE_WORKERS', '1'))

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please login to access this page.'
login_manager.login_message_category = 'info'

# Initialize User Manager and Database
user_manager = UserManager()
db = Database()

@login_manager.user_loader
def load_user(user_id):
    return user_manager.get_user_by_id(user_id)


@app.context_processor
def inject_unread_inbox():
    """Makes has_unread_inbox available in every template (base.html nav dot)
    without threading it through every route. Cheap EXISTS check, not a count."""
    if not current_user.is_authenticated:
        return {'has_unread_inbox': False}
    return {'has_unread_inbox': db.has_unread_inbox_messages(current_user.id)}


@app.template_filter('ist_time')
def format_ist_time(ts):
    """Format a stored inbox timestamp for display.

    Stored timestamps (inbox_messages.created_at, and messages.replied_at
    once normalized by _parse_legacy_ts) are naive strings from
    datetime.now() / datetime.fromtimestamp() — both of which already
    return server-local time. Per CLAUDE.md, the production server's
    timezone is set to IST (`timedatectl set-timezone Asia/Kolkata`), so
    these values ARE ALREADY IST. This only formats for readability — it
    must NOT apply a UTC->IST offset, which would double-shift an
    already-correct value.
    """
    if not ts:
        return ''
    try:
        dt = datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return ts[:16] if isinstance(ts, str) else ''
    return dt.strftime('%d %b, %I:%M %p')

# Initialize GLOBAL rate limiter and message queue
# These persist across requests
rate_limiter = RateLimiter(max_requests=MAX_REQUESTS, time_window=TIME_WINDOW)
message_queue = MessageQueue(rate_limiter, num_workers=NUM_WORKERS)
message_queue.start()  # Start worker threads

logger.info("✅ Message queue started successfully")
logger.info(f"⚙️ Rate limit: {MAX_REQUESTS} requests per {TIME_WINDOW}s with {NUM_WORKERS} worker(s)")

# Connect message queue to scheduler
from utils.background_scheduler import set_message_queue, set_waba_id
set_message_queue(message_queue)
set_waba_id(WABA_ID)


# ============================================================
# AUTOMATION HELPERS
# ============================================================

def _format_items(line_items, max_items=3):
    """Format line_items list into a short readable string, including size/colour.

    Examples:
        Blue Sneakers (Size 9 / White) x2, Black Jeans (30 / Regular)
        Nike Cap & 2 more
    """
    if not line_items:
        return 'your items'
    parts = []
    for item in line_items[:max_items]:
        title   = item.get('title') or item.get('name') or 'Item'
        qty     = int(item.get('quantity') or 1)
        variant = (item.get('variant_title') or '').strip()
        # Omit generic Shopify default variant placeholder
        if variant and variant.lower() not in ('default title', 'default'):
            display = f"{title} ({variant})"
        else:
            display = title
        parts.append(f"{display} x{qty}" if qty > 1 else display)
    result = ', '.join(parts)
    extra  = len(line_items) - max_items
    if extra > 0:
        result += f" & {extra} more"
    return result


def _fetch_order_status_url(shopify_order_id):
    """Fetch Shopify's customer-facing order_status_url for one order via the Admin API.

    Used by /track/<order_ref> to self-heal orders fulfilled before the
    order_status_url column existed. Needs the read_orders scope on
    SHOPIFY_ACCESS_TOKEN; returns None (and logs why) on any failure so the
    caller falls through to the AWB-only page.
    """
    if not shopify_order_id:
        return None
    shop  = os.getenv('SHOPIFY_SHOP_NAME', '')
    token = os.getenv('SHOPIFY_ACCESS_TOKEN', '')
    if not (shop and token):
        return None
    try:
        import requests as _req
        url = (f"https://{shop}.myshopify.com/admin/api/2024-01/orders/"
               f"{shopify_order_id}.json?fields=order_status_url")
        resp = _req.get(url, headers={"X-Shopify-Access-Token": token}, timeout=10)
        if resp.status_code == 200:
            status_url = (resp.json().get('order') or {}).get('order_status_url')
            if status_url:
                logger.info(f"order_status_url backfilled from Shopify for {shopify_order_id}")
            return status_url or None
        if resp.status_code == 403:
            logger.warning("Shopify orders API returned 403 — SHOPIFY_ACCESS_TOKEN "
                           "lacks read_orders scope; /track/ cannot backfill old orders")
        else:
            logger.warning(f"Shopify orders API returned {resp.status_code} "
                           f"for order {shopify_order_id}")
    except Exception as e:
        logger.warning(f"Could not fetch order_status_url from Shopify: {e}")
    return None


def _get_product_image_url(line_items):
    """Return the src URL of the first product image from a Shopify line_items list.

    Shopify order webhooks often don't include line_items[].image.src, so we
    fall back to the Shopify Admin API using the product_id from the line item.
    """
    if not line_items:
        return None

    # 1. Try webhook payload directly (works sometimes)
    for item in line_items:
        img = item.get('image') or {}
        src = img.get('src') or img.get('url')
        if src:
            return src

    # 2. Fetch from Shopify Admin API using product_id
    product_id = line_items[0].get('product_id')
    if product_id:
        try:
            import requests as _req
            shop  = os.getenv('SHOPIFY_SHOP_NAME', '')
            token = os.getenv('SHOPIFY_ACCESS_TOKEN', '')
            if shop and token:
                url = f"https://{shop}.myshopify.com/admin/api/2024-01/products/{product_id}.json"
                resp = _req.get(url,
                                headers={"X-Shopify-Access-Token": token},
                                timeout=10)
                if resp.status_code == 200:
                    images = resp.json().get('product', {}).get('images', [])
                    if images:
                        src = images[0].get('src')
                        logger.info(f"Product image fetched from Shopify API: {src}")
                        return src
                else:
                    logger.warning(f"Shopify product image API returned {resp.status_code} for product {product_id}")
        except Exception as e:
            logger.warning(f"Could not fetch product image from Shopify API: {e}")

    return None


_MEDIA_HEADER_CONTENT_TYPES = {
    # WhatsApp's accepted MIME types per header media type, and the fallback used
    # when a server doesn't send a (useful) Content-Type — same graceful-degrade
    # shape as the original image-only version of this function.
    'image': ({'image/jpeg', 'image/png', 'image/jpg'}, 'image/jpeg'),
    'video': ({'video/mp4', 'video/3gpp'}, 'video/mp4'),
    'document': ({'application/pdf'}, 'application/pdf'),
}


def _upload_media_from_url(media_url, media_type='image'):
    """Download a file from a URL and upload it to WhatsApp as a header media_id.
    `media_type` is 'image', 'video', or 'document' (matches send_template()'s
    header_media_type). Returns media_id or None — non-fatal, same as the
    image-only version this generalizes."""
    if not media_url:
        return None
    accepted_types, fallback_type = _MEDIA_HEADER_CONTENT_TYPES.get(
        media_type, _MEDIA_HEADER_CONTENT_TYPES['image'])
    try:
        import requests as _requests
        resp = _requests.get(media_url, timeout=15)
        if resp.status_code != 200:
            logger.warning(f"Could not download {media_type} ({resp.status_code}): {media_url}")
            return None
        content_type = resp.headers.get('Content-Type', fallback_type).split(';')[0].strip()
        if content_type not in accepted_types:
            content_type = fallback_type
        media_id = upload_media_from_bytes(resp.content, content_type)
        if media_id:
            logger.info(f"{media_type.capitalize()} uploaded to WhatsApp: {media_id}")
        return media_id
    except Exception as e:
        logger.warning(f"{media_type.capitalize()} upload failed (non-fatal): {e}")
        return None


def _upload_image_from_url(image_url):
    """Download an image from a URL and upload it to WhatsApp. Returns media_id or None."""
    return _upload_media_from_url(image_url, 'image')


def _get_webhook_user_id():
    """Return the user_id to use for webhook processing.

    Prefers the user who has automation settings saved (the real owner),
    then the most recently active user, then the first user in users.json.
    This prevents the bug where users[0] has id='1' but the actual
    logged-in user has a different id.
    """
    # 1. User with automation settings configured
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM automation_settings LIMIT 1')
            row = cursor.fetchone()
            if row:
                return row[0]
    except Exception:
        pass

    # 2. Most recently active user
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT user_id FROM activity_log ORDER BY timestamp DESC LIMIT 1'
            )
            row = cursor.fetchone()
            if row:
                return row[0]
    except Exception:
        pass

    # 3. Fall back to first user
    users = user_manager.get_all_users()
    return users[0].id if users else None


def _normalize_phone_webhook(phone):
    """Normalize a phone number from Shopify webhooks to E.164 (+91XXXXXXXXXX)."""
    if not phone:
        return None
    cleaned = ''.join(c for c in str(phone) if c.isdigit() or c == '+')
    if not cleaned:
        return None
    if cleaned.startswith('+'):
        return cleaned
    elif len(cleaned) == 12 and cleaned.startswith('91'):
        return '+' + cleaned
    elif len(cleaned) == 11 and cleaned.startswith('0'):
        return '+91' + cleaned[1:]
    elif len(cleaned) == 10:
        return '+91' + cleaned
    return '+' + cleaned


def _has_active_flow(user_id, trigger_type):
    """True if a Flows automation is active for this trigger type.

    Used to make Flows and the legacy automation_settings mutually exclusive per
    event type — whichever system is active for a trigger owns it, so a customer
    never gets the same notification twice.
    """
    return bool(db.get_active_flows_by_trigger(user_id, trigger_type))


def _verify_shopify_hmac(raw_data, hmac_header):
    """Verify Shopify webhook HMAC-SHA256 signature.
    Returns True if valid, or if SHOPIFY_WEBHOOK_SECRET is not configured."""
    secret = os.getenv('SHOPIFY_WEBHOOK_SECRET', '')
    if not secret:
        return True  # Permissive when no secret is set
    if not hmac_header:
        logger.warning("Shopify webhook missing HMAC header")
        return False
    h = hmac.new(secret.encode('utf-8'), raw_data, hashlib.sha256)
    computed = base64.b64encode(h.digest()).decode('utf-8')
    return hmac.compare_digest(computed, hmac_header)


def _template_shape(template_name, template_language=None):
    """Inspect the approved WhatsApp template and return how it expects to be filled.

    Returns {'body_vars': int, 'has_dynamic_url_button': bool}, or None if the
    template can't be looked up (API error, not found). Callers must fall back to
    their previous fixed assumptions on None so a Meta outage never blocks sends.

    Lets the sender adapt to whatever is currently approved — add or remove a
    body variable or a URL button in Business Manager and the payload follows,
    instead of failing with 132000 (param count) or 132018 (button params).
    """
    if not (WABA_ID and template_name):
        return None
    try:
        candidates = [t for t in get_templates(WABA_ID) if t.get('name') == template_name]
        if not candidates:
            logger.warning(f"_template_shape: template '{template_name}' not found")
            return None
        # Prefer exact language match, then APPROVED, then whatever's first.
        def rank(t):
            return (t.get('language') != template_language, t.get('status') != 'APPROVED')
        tmpl = sorted(candidates, key=rank)[0]

        body_vars = 0
        has_dyn_url = False
        for comp in tmpl.get('components', []):
            ctype = comp.get('type')
            if ctype == 'BODY':
                nums = [int(n) for n in re.findall(r'\{\{(\d+)\}\}', comp.get('text') or '')]
                body_vars = max(nums) if nums else 0
            elif ctype == 'BUTTONS':
                for b in comp.get('buttons', []):
                    if b.get('type') == 'URL' and '{{' in (b.get('url') or ''):
                        has_dyn_url = True
        return {'body_vars': body_vars, 'has_dynamic_url_button': has_dyn_url}
    except Exception as e:
        logger.warning(f"_template_shape: could not inspect '{template_name}': {e}")
        return None


def _send_automation_message(phone, event_type, template_name, template_language, params,
                             header_media_id=None, button_params=None):
    """Send a single automation WhatsApp template message. Returns (success, wamid)."""
    try:
        status_code, response = send_template(
            phone, template_name, params,
            lang=template_language,
            header_media_id=header_media_id,
            button_params=button_params
        )
        success = status_code in [200, 201]
        wamid = None
        if success:
            msgs = response.get('messages', [])
            wamid = msgs[0].get('id') if msgs else None
        logger.info(
            f"{'✅' if success else '❌'} Automation [{event_type}] → {phone}: "
            f"HTTP {status_code}"
        )
        return success, wamid
    except Exception as e:
        logger.error(f"❌ Automation send exception [{event_type}] → {phone}: {e}")
        return False, None


def _start_abandoned_cart_checker():
    """Start a daemon thread that sends abandoned-cart reminders every 15 minutes."""

    def _checker():
        while True:
            try:
                time.sleep(15 * 60)  # wait first, then check
                logger.debug("🛒 Abandoned-cart checker running…")
                users = user_manager.get_all_users()
                for user in users:
                    settings = db.get_automation_settings(user.id)
                    s = settings.get('abandoned_cart', {})
                    if not s.get('enabled'):
                        continue
                    if _has_active_flow(user.id, 'abandoned_cart'):
                        # A Flows automation already owns this trigger — skip the
                        # legacy path to avoid sending the reminder twice.
                        logger.info(f"Skipping legacy abandoned_cart automation for user {user.id} — active flow owns this trigger")
                        continue
                    template_name = (s.get('template_name') or '').strip()
                    template_language = s.get('template_language') or 'en_US'
                    delay_hours = int(s.get('delay_hours') or 1)
                    if not template_name:
                        continue

                    carts = db.get_abandoned_carts_ready_for_reminder(user.id, delay_hours)
                    for cart in carts:
                        phone = _normalize_phone_webhook(cart.get('customer_phone'))
                        if not phone:
                            continue

                        # Safety check: skip if the customer placed an order after abandoning
                        # (handles cases where mark_cart_recovered failed due to token mismatch)
                        try:
                            with db.get_connection() as conn:
                                cursor = conn.cursor()
                                cursor.execute('''
                                    SELECT COUNT(*) as cnt FROM shopify_orders
                                    WHERE customer_phone = ?
                                    AND created_at > ?
                                ''', (phone, cart['abandoned_at']))
                                row = cursor.fetchone()
                                if row and row['cnt'] > 0:
                                    db.mark_cart_recovered_by_id(cart['id'])
                                    logger.info(f"⏭️ Skipping cart {cart['id']} — {phone} placed an order after abandoning")
                                    continue
                        except Exception as e:
                            logger.warning(f"Could not check order status for cart {cart['id']}: {e}")

                        cart_items = json.loads(cart['cart_items']) if cart['cart_items'] else []
                        items_str = _format_items(cart_items)
                        total = cart.get('total_price') or '0'
                        # Use stored name; fall back to customers table; last resort 'there'
                        first_name = (cart.get('customer_name') or '').strip()
                        if not first_name:
                            try:
                                with db.get_connection() as conn:
                                    cursor = conn.cursor()
                                    cursor.execute(
                                        'SELECT first_name FROM customers WHERE phone = ? LIMIT 1',
                                        (phone,)
                                    )
                                    row = cursor.fetchone()
                                    if row and row['first_name']:
                                        first_name = row['first_name']
                            except Exception:
                                pass
                        if not first_name:
                            first_name = 'there'

                        # Template params: {{1}}=name, {{2}}=items, {{3}}=total
                        # Discount code and website button are hardcoded in the template itself
                        params = [first_name, items_str, f"₹{total}"]

                        success, _ = _send_automation_message(
                            phone, 'abandoned_cart', template_name, template_language, params
                        )
                        if success:
                            db.mark_cart_reminder_sent(cart['id'])
                            db.log_activity(
                                user_id=user.id,
                                username='System',
                                action='Automation: Cart Reminder Sent',
                                details=f"Cart #{cart.get('shopify_cart_id')} → {phone}"
                            )
                            logger.info(f"✅ Cart reminder sent to {phone}")
                        else:
                            logger.warning(f"⚠️ Cart reminder failed for {phone}")
            except Exception as exc:
                logger.error(f"❌ Abandoned-cart checker error: {exc}", exc_info=True)

    t = threading.Thread(target=_checker, daemon=True, name='abandoned_cart_checker')
    t.start()
    logger.info("✅ Abandoned-cart background checker started")


# Start abandoned-cart background checker
_start_abandoned_cart_checker()

# Start flow engine
start_flow_engine(db, message_queue)


# ============================================================
# AUTHENTICATION ROUTES
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    """Login page"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == "POST":
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'
        
        if not username or not password:
            flash("Please enter both username and password", "error")
            return redirect(url_for('login'))
        
        # Authenticate user
        user = user_manager.authenticate(username, password)
        
        if user:
            login_user(user, remember=remember)
            logger.info(f"User logged in: {user.username}")
            
            # Log activity
            db.log_activity(
                user_id=user.id,
                username=user.username,
                action='Login',
                details='User logged in',
                ip_address=request.remote_addr
            )
            
            # Create session
            db.create_session(
                user_id=user.id,
                username=user.username,
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string
            )
            
            # Redirect to next page or dashboard
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('index'))
        else:
            flash("Invalid username or password", "error")
            return redirect(url_for('login'))
    
    return render_template('login.html')


@app.route("/signup")
def signup():
    flash("Registration is closed. Contact the admin for access.", "error")
    return redirect(url_for('login'))


@app.route("/logout")
@login_required
def logout():
    """Logout user"""
    user_id = current_user.id
    username = current_user.username
    
    # Log activity
    db.log_activity(
        user_id=user_id,
        username=username,
        action='Logout',
        details='User logged out',
        ip_address=request.remote_addr
    )
    
    logout_user()
    logger.info(f"User logged out: {username}")
    flash("You have been logged out successfully", "success")
    return redirect(url_for('login'))


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def validate_phone_number(phone):
    """
    Validate phone number format
    Returns True if valid, False otherwise
    """
    if not phone:
        return False
    
    # Remove common formatting characters
    digits = ''.join(c for c in str(phone) if c.isdigit())
    
    # Check length (10-15 digits is standard for international numbers)
    if len(digits) < 10 or len(digits) > 15:
        return False
    
    return True


# ============================================================
# TEMPLATE ROUTES
# ============================================================

@app.route("/templates")
@login_required
def templates_manager():
    """View and manage all WhatsApp message templates"""
    try:
        from utils.whatsapp import get_templates as fetch_templates
        templates = fetch_templates(WABA_ID)
    except Exception as e:
        logger.error(f"Error fetching templates: {e}")
        templates = []
    return render_template("templates_manager.html", templates=templates)


@app.route("/api/templates/delete", methods=["POST"])
@login_required
def api_delete_template():
    """Delete a WhatsApp template by name"""
    data = request.get_json()
    template_name = data.get("name") if data else None
    if not template_name:
        return jsonify({"success": False, "error": "Template name required"}), 400
    from utils.whatsapp import delete_template
    status, resp = delete_template(WABA_ID, template_name)
    if status == 200:
        return jsonify({"success": True})
    error_msg = resp.get("error", {}).get("message", "Unknown error") if isinstance(resp, dict) else str(resp)
    return jsonify({"success": False, "error": error_msg}), status


@app.route("/create-template", methods=["GET"])
@login_required
def create_template_page():
    """Render template creation page"""
    return render_template("create_template.html")


@app.route("/submit-template", methods=["POST"])
@login_required
def submit_template():
    """Handle template submission to WhatsApp"""
    try:
        template_data = {
            'template_name': request.form.get('template_name'),
            'category': request.form.get('category'),
            'language': request.form.get('language'),
            'header_type': request.form.get('header_type'),
            'header_text': request.form.get('header_text'),
            'header_image_url': request.form.get('header_image_url'),
            'body_text': request.form.get('body_text'),
            'footer_text': request.form.get('footer_text'),
        }
        
        # Get button data
        for i in range(1, 4):
            template_data[f'button_type_{i}'] = request.form.get(f'button_type_{i}')
            template_data[f'button_text_{i}'] = request.form.get(f'button_text_{i}')
            template_data[f'button_value_{i}'] = request.form.get(f'button_value_{i}')
        
        # Get header media file if provided (image/video/document all share this
        # one file input -- only one header type is active at a time in the form)
        header_media_file = request.files.get('header_image')

        if header_media_file and header_media_file.filename:
            logger.info(f"📎 Received header media file: {header_media_file.filename}")
            # Get file size
            header_media_file.seek(0, 2)
            file_size = header_media_file.tell()
            header_media_file.seek(0)
            logger.info(f"📎 File size: {file_size} bytes")

        from utils.whatsapp import create_template

        status, response = create_template(WABA_ID, template_data, header_media_file)
        
        if status in [200, 201]:
            flash(f"✅ Template '{template_data['template_name']}' submitted successfully! It will be reviewed by WhatsApp.", "success")
            return redirect("/create-template")
        else:
            error_msg = "Unknown error"
            if 'error' in response:
                if isinstance(response['error'], dict):
                    error_msg = response['error'].get('message', str(response['error']))
                else:
                    error_msg = str(response['error'])
            
            flash(f"❌ Error: {error_msg}", "error")
            logger.error(f"Template creation error: {response}")
            return redirect("/create-template")
    
    except Exception as e:
        import traceback
        logger.error(f"Exception in submit_template: {traceback.format_exc()}")
        flash(f"❌ Error creating template: {str(e)}", "error")
        return redirect("/create-template")


# ============================================================
# UTILITY ROUTES
# ============================================================

@app.route("/get-csv-columns", methods=["POST"])
@login_required
def get_csv_columns():
    """Get column names from uploaded CSV"""
    csv_file = request.files.get("csv_file")
    if not csv_file:
        return jsonify({"error": "No file uploaded"}), 400
    
    try:
        import pandas as pd
        df = pd.read_csv(csv_file)
        columns = list(df.columns)
        return jsonify({"columns": columns})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/template-info")
@login_required
def template_info():
    """Get template parameter count and button information"""
    template_name = request.args.get("name")
    templates = get_templates(WABA_ID)

    selected = next((t for t in templates if t["name"] == template_name), None)

    count = 0
    buttons = []
    has_header_param = False
    header_media_type = None   # 'image' | 'video' | 'document', when the header takes a media id
    header_location = False    # LOCATION header — different shape (lat/lng/name/address), no media id

    if selected:
        body = next((c for c in selected["components"] if c["type"] == "BODY"), None)
        if body and "text" in body:
            count = body["text"].count("{{")

        # A template's HEADER is exactly one of TEXT (with a {{1}} variable, at
        # most one), IMAGE/VIDEO/DOCUMENT (all take a media id, just a different
        # WhatsApp API 'type'), or LOCATION (lat/lng/name/address — no media id at
        # all) — mirrors send_template()'s header_param/header_media_id being
        # mutually exclusive.
        header = next((c for c in selected["components"] if c["type"] == "HEADER"), None)
        header_format = (header or {}).get("format")
        if header_format == "TEXT" and "{{1}}" in header.get("text", ""):
            has_header_param = True
        elif header_format in ("IMAGE", "VIDEO", "DOCUMENT"):
            header_media_type = header_format.lower()
        elif header_format == "LOCATION":
            header_location = True

        # Check for buttons component
        buttons_component = next((c for c in selected["components"] if c["type"] == "BUTTONS"), None)
        if buttons_component and "buttons" in buttons_component:
            for idx, btn in enumerate(buttons_component["buttons"]):
                btn_type = btn.get("type", "")
                btn_text = btn.get("text", "")
                
                # Map button types to required parameters
                if btn_type == "COPY_CODE":
                    buttons.append({
                        "index": idx,
                        "type": "COPY_CODE",
                        "text": btn_text,
                        "requires": "coupon_code"
                    })
                elif btn_type == "URL" and "{{1}}" in btn.get("url", ""):
                    buttons.append({
                        "index": idx,
                        "type": "URL",
                        "text": btn_text,
                        "requires": "url_parameter"
                    })
                elif btn_type == "CATALOG":
                    # No per-recipient data needed -- WhatsApp fills the catalog
                    # itself. Reported so callers know it exists (e.g. to avoid
                    # blocking the template), not because it needs a config row.
                    buttons.append({
                        "index": idx,
                        "type": "CATALOG",
                        "text": btn_text,
                        "requires": None
                    })

    return jsonify({"count": count, "buttons": buttons, "has_header_param": has_header_param,
                     "header_media_type": header_media_type, "header_location": header_location})


@app.route("/queue-stats")
@login_required
def queue_stats():
    """Get current message queue statistics"""
    stats = message_queue.get_stats()
    return jsonify(stats)


@app.route("/queue-monitor")
@login_required
def queue_status_page():
    """Render queue status monitoring page"""
    return render_template("queue_status.html")


# ============================================================
# SCHEDULED JOBS ROUTES
# ============================================================

@app.route("/scheduled-jobs")
@login_required
def scheduled_jobs():
    """View scheduled jobs"""
    jobs = get_scheduled_jobs()
    return jsonify({"jobs": jobs})


@app.route("/cancel-job/<job_id>", methods=["POST"])
@login_required
def cancel_scheduled_job(job_id):
    """Cancel a scheduled job"""
    success, message = cancel_job(job_id)
    return jsonify({"success": success, "message": message})


# ============================================================
# MAIN MESSAGE SENDING ROUTE
# ============================================================

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Main page for sending WhatsApp messages"""
    results = []
    templates = get_templates(WABA_ID)

    template_param_count = 0
    csv_columns = []

    if request.method == "POST":
        source_type = request.form.get("source_type", "csv")
        csv_file = request.files.get("csv_file")
        selected_customers = request.form.get("selected_customers")
        template_name = request.form.get("template_name")
        message_template = request.form.get("message_template")
        send_mode = request.form.get("send_mode")
        send_time = request.form.get("send_time")

        # Handle customer-based sending
        if source_type == "customers" and selected_customers:
            try:
                import pandas as pd
                import json
                customers = json.loads(selected_customers)
                
                # Convert to DataFrame format
                df = pd.DataFrame(customers)
                df = df.rename(columns={'phone': 'Phone', 'name': 'Name'})
                
            except Exception as e:
                flash(f"❌ Error processing selected customers: {str(e)}", "error")
                return redirect("/")
        
        # Handle CSV-based sending
        elif source_type == "csv":
            # Validate CSV upload
            if not csv_file:
                flash("Please upload CSV.", "error")
                return redirect("/")
            
            # Validate file extension
            if not csv_file.filename.lower().endswith('.csv'):
                flash("❌ Please upload a CSV file (not Excel or other formats)", "error")
                return redirect("/")

            # Validate file size (5MB limit)
            csv_file.seek(0, os.SEEK_END)
            file_size = csv_file.tell()
            csv_file.seek(0)
            
            if file_size > 5 * 1024 * 1024:  # 5MB
                flash("❌ File too large. Maximum 5MB allowed.", "error")
                return redirect("/")

            # Read CSV with encoding fallback
            try:
                import pandas as pd
                df = pd.read_csv(csv_file, encoding='utf-8')
            except UnicodeDecodeError:
                logger.warning("UTF-8 decode failed, trying latin-1 encoding")
                csv_file.seek(0)
                try:
                    import pandas as pd
                    df = pd.read_csv(csv_file, encoding='latin-1')
                except Exception as e:
                    flash(f"❌ Error reading CSV: {str(e)}", "error")
                    return redirect("/")
            except Exception as e:
                flash(f"❌ Error reading CSV: {str(e)}", "error")
                return redirect("/")
        else:
            flash("❌ Please select a data source (CSV or Customers)", "error")
            return redirect("/")

        # Check if DataFrame is empty
        if len(df) == 0:
            flash("❌ No contacts found. Please add contacts.", "error")
            return redirect("/")

        csv_columns = list(df.columns)

        # Validate required columns
        if "Phone" not in csv_columns:
            flash("CSV must contain a 'Phone' column.", "error")
            return redirect("/")

        # Validate phone numbers
        invalid_phones = []
        for idx, row in df.iterrows():
            phone = str(row.get("Phone", ""))
            if not validate_phone_number(phone):
                invalid_phones.append(f"Row {idx + 2}: {phone}")  # +2 for header + 0-indexed
        
        if invalid_phones:
            if len(invalid_phones) <= 5:
                flash(f"❌ Invalid phone numbers found:\n" + "\n".join(invalid_phones[:5]), "error")
            else:
                flash(f"❌ Found {len(invalid_phones)} invalid phone numbers. First 5:\n" + "\n".join(invalid_phones[:5]), "error")
            return redirect("/")

        # Limit number of recipients
        if len(df) > 10000:
            flash("❌ Too many recipients. Maximum 10,000 per batch.", "error")
            return redirect("/")

        # Get template info
        selected_template = next((t for t in templates if t["name"] == template_name), None)
        template_language = "en"
        template_buttons = []

        if selected_template:
            template_language = selected_template.get("language", "en")
            body_component = next(
                (c for c in selected_template["components"] if c["type"] == "BODY"),
                None
            )
            if body_component and "text" in body_component:
                template_param_count = body_component["text"].count("{{")
            
            # Extract button information
            buttons_component = next(
                (c for c in selected_template["components"] if c["type"] == "BUTTONS"),
                None
            )
            if buttons_component and "buttons" in buttons_component:
                for idx, btn in enumerate(buttons_component["buttons"]):
                    btn_type = btn.get("type", "")
                    if btn_type == "COPY_CODE":
                        template_buttons.append({
                            "index": idx,
                            "type": "COPY_CODE",
                            "text": btn.get("text", ""),
                            "form_key": f"button_coupon_code_{idx}"
                        })
                    elif btn_type == "URL" and "{{1}}" in btn.get("url", ""):
                        template_buttons.append({
                            "index": idx,
                            "type": "URL",
                            "text": btn.get("text", ""),
                            "form_key": f"button_url_param_{idx}"
                        })
        # ----------------------------
        # Check for IMAGE header
        # ----------------------------
        header_needs_image = False
        header_media_id = None

        if selected_template:
            header_component = next(
                (c for c in selected_template["components"] if c["type"] == "HEADER"),
                None
            )
            if header_component and header_component.get("format") == "IMAGE":
                header_needs_image = True
        
        if selected_template and header_needs_image:
            image_file = request.files.get("header_image")
        
            if not image_file or image_file.filename == "":
                flash("This template requires an IMAGE header. Please upload a header image.", "error")
                return redirect("/")
        
            header_media_id = upload_media(image_file)
        
            if not header_media_id:
                flash("Header image upload failed. Please try again.", "error")
                return redirect("/")

        # ==============================================================
        # SCHEDULED SENDING
        # ==============================================================
        if send_mode == "later":
            schedule_date = request.form.get("schedule_date")
            schedule_time = request.form.get("schedule_time")
            
            if not schedule_date or not schedule_time:
                flash("Please select both date and time for scheduling.", "error")
                return redirect("/")
            
            # Combine date and time into full datetime string
            schedule_datetime_str = f"{schedule_date} {schedule_time}"
            
            # Validate that scheduled time is in the future
            try:
                scheduled_dt = datetime.strptime(schedule_datetime_str, "%Y-%m-%d %H:%M")
                now = datetime.now()
                
                if scheduled_dt <= now:
                    flash("Scheduled time must be in the future.", "error")
                    return redirect("/")
                
                # Calculate time until execution
                time_diff = scheduled_dt - now
                days = time_diff.days
                hours = time_diff.seconds // 3600
                minutes = (time_diff.seconds % 3600) // 60
                
                if days > 0:
                    time_msg = f"{days} day(s) and {hours} hour(s)"
                elif hours > 0:
                    time_msg = f"{hours} hour(s) and {minutes} minute(s)"
                else:
                    time_msg = f"{minutes} minute(s)"
                    
            except ValueError:
                flash("Invalid date/time format.", "error")
                return redirect("/")
            
            # Prepare parameters for scheduled job
            if selected_template:
                params_mapping = []
                for i in range(template_param_count):
                    col = request.form.get(f"param{i+1}")
                    if not col:
                        flash(f"Please map all template parameters.", "error")
                        return redirect("/")
                    params_mapping.append(col)
                
                # Extract button parameters for scheduled messages
                scheduled_button_params = {}
                for btn in template_buttons:
                    if btn["type"] == "COPY_CODE":
                        coupon_code = request.form.get(btn["form_key"])
                        if coupon_code:
                            scheduled_button_params["copy_code"] = str(coupon_code)
                            scheduled_button_params["copy_code_index"] = btn["index"]
                    elif btn["type"] == "URL":
                        url_param_col = request.form.get(btn["form_key"])
                        if url_param_col:
                            # For scheduled messages, we'll need to pass the column name
                            # and extract value per recipient during sending
                            scheduled_button_params[f"url_column_{btn['index']}"] = url_param_col
                
                success, message = schedule_message_job(
                    df=df,
                    template_name=template_name,
                    template_language=template_language,
                    template_params_mapping=params_mapping,
                    send_time_str=schedule_datetime_str,
                    header_media_id=header_media_id,
                    button_params=scheduled_button_params if scheduled_button_params else None,
                    user_id=current_user.id,
                    username=current_user.username
                )
            else:
                if not message_template:
                    flash("Please enter a message template.", "error")
                    return redirect("/")
                
                success, message = schedule_message_job(
                    df=df,
                    message_template=message_template,
                    send_time_str=schedule_datetime_str,
                    user_id=current_user.id,
                    username=current_user.username
                )
            
            if success:
                flash(f"✅ Messages scheduled for {scheduled_dt.strftime('%Y-%m-%d %H:%M')} ({time_msg} from now). They will be sent automatically even when you're logged out.", "success")
            else:
                flash(f"❌ {message}", "error")
            
            return redirect("/")

        # ==============================================================
        # IMMEDIATE SENDING (WITH RATE LIMITING)
        # ==============================================================
        
        # Resolve campaign — new or add to existing
        campaign_mode = request.form.get("campaign_mode", "new")
        campaign_type = 'Template' if selected_template else 'Text'
        logger.info(f"Campaign form received: mode={campaign_mode!r}, name_new={request.form.get('campaign_name_new')!r}")

        if campaign_mode == "existing":
            try:
                campaign_id = int(request.form.get("campaign_id_existing", ""))
                existing = db.get_campaign(campaign_id)
                if not existing or existing['user_id'] != current_user.id:
                    flash("❌ Invalid campaign selected.", "error")
                    return redirect("/")
                campaign_name = existing['campaign_name']
                db.add_to_campaign_recipient_count(campaign_id, len(df))
                db.update_campaign_status(campaign_id, 'running')
            except (ValueError, TypeError):
                flash("❌ Invalid campaign selected.", "error")
                return redirect("/")
        else:
            campaign_name = request.form.get("campaign_name_new", "").strip()
            if not campaign_name:
                campaign_name = f"Campaign {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            campaign_id = db.create_campaign(
                user_id=current_user.id,
                username=current_user.username,
                campaign_name=campaign_name,
                campaign_type=campaign_type,
                template_name=template_name if selected_template else None,
                recipient_count=len(df),
                scheduled_time=None
            )
            db.update_campaign_status(campaign_id, 'running')

        # Log campaign send
        db.log_activity(
            user_id=current_user.id,
            username=current_user.username,
            action='Campaign Started' if campaign_mode != 'existing' else 'Campaign Batch Added',
            details=f"Campaign: {campaign_name}, Recipients: {len(df)}, Type: {campaign_type}",
            ip_address=request.remote_addr
        )
        
        if selected_template:
            # Validate parameters mapping
            if any(request.form.get(f"param{i+1}") is None for i in range(template_param_count)):
                return render_template(
                    "index.html",
                    results=results,
                    templates=templates,
                    template_param_count=template_param_count,
                    csv_columns=csv_columns
                )

            # Add all template messages to queue
            for idx, row in df.iterrows():
                row_dict = row.to_dict()
                name = row_dict.get("Name", "")
                phone = str(row_dict.get("Phone"))

                params = []
                for i in range(template_param_count):
                    col = request.form.get(f"param{i+1}")
                    val = row_dict.get(col)

                    if val is None:
                        flash(f"Column '{col}' missing in CSV", "error")
                        return redirect("/")

                    params.append(str(val))
                
                # Prepare button parameters if template has buttons
                button_params = {}
                for btn in template_buttons:
                    if btn["type"] == "COPY_CODE":
                        # Get coupon code directly from form (same for all recipients)
                        coupon_code = request.form.get(btn["form_key"])
                        if coupon_code:
                            button_params["copy_code"] = str(coupon_code)
                            button_params["copy_code_index"] = btn["index"]  # Add button index
                    elif btn["type"] == "URL":
                        # Get URL parameter from CSV column (unique per recipient)
                        url_param_col = request.form.get(btn["form_key"])
                        if url_param_col:
                            url_value = row_dict.get(url_param_col)
                            if url_value:
                                button_params[f"url_index_{btn['index']}"] = str(url_value)

                # Add message record to database
                message_id = db.add_message(
                    campaign_id=campaign_id,
                    user_id=current_user.id,
                    phone_number=phone,
                    recipient_name=name,
                    template_name=template_name,
                    status='queued',
                    template_params=params,
                    template_language=template_language,
                    button_params=button_params if button_params else None,
                    header_media_id=header_media_id
                )

                # Add to queue instead of sending immediately
                message_queue.add_message(
                    send_template,
                    phone,
                    template_name,
                    params,
                    template_language,
                    header_media_id=header_media_id,
                    button_params=button_params if button_params else None,
                    user_id=current_user.id,
                    username=current_user.username,
                    campaign_id=campaign_id,
                    message_id=message_id
                )

            flash(f"✅ {len(df)} messages queued for campaign \"{campaign_name}\". Monitor progress at /queue-status", "success")
            return redirect("/")

        else:
            # Free text messages
            if not message_template:
                flash("Please enter a message template.", "error")
                return redirect("/")

            for idx, row in df.iterrows():
                row_dict = row.to_dict()
                name = row_dict.get("Name", "")
                phone = str(row_dict.get("Phone")).strip()

                personalized_msg = personalize(message_template, row_dict, idx + 1)
                
                # Add message record to database
                message_id = db.add_message(
                    campaign_id=campaign_id,
                    user_id=current_user.id,
                    phone_number=phone,
                    recipient_name=name,
                    message_content=personalized_msg,
                    status='queued'
                )

                # Add to queue
                message_queue.add_message(
                    send_text,
                    phone,
                    personalized_msg,
                    user_id=current_user.id,
                    username=current_user.username,
                    campaign_id=campaign_id,
                    message_id=message_id
                )

            flash(f"✅ {len(df)} messages queued for campaign \"{campaign_name}\". Monitor progress at /queue-status", "success")
            return redirect("/")

    recent_campaigns = db.get_user_campaigns(current_user.id, limit=15)
    return render_template(
        "index.html",
        results=results,
        templates=templates,
        template_param_count=template_param_count,
        csv_columns=csv_columns,
        current_date=datetime.now().strftime('%Y-%m-%d'),
        recent_campaigns=recent_campaigns
    )


# ============================================================
# ANALYTICS & REPORTING ROUTES
# ============================================================

@app.route("/analytics")
@login_required
def analytics_dashboard():
    """Analytics dashboard"""
    # Get statistics
    stats = db.get_dashboard_stats(user_id=current_user.id)
    
    # Get campaigns
    campaigns = db.get_user_campaigns(current_user.id, limit=10)
    
    # Get template stats
    template_stats = db.get_template_stats(user_id=current_user.id)
    
    # Get recent activity
    recent_activity = db.get_user_activity(current_user.id, limit=10)
    
    # Get chart data
    chart_stats = db.get_campaign_stats_by_date(user_id=current_user.id, days=30)
    
    # Prepare chart data - always show last 30 days
    from datetime import datetime, timedelta
    today = datetime.now().date()
    
    # Create a dict of dates to counts
    date_counts = {}
    if chart_stats:
        for stat in chart_stats:
            date_counts[stat['date']] = stat['count']
    
    # Generate last 30 days
    dates = []
    counts = []
    for i in range(29, -1, -1):
        date = (today - timedelta(days=i)).strftime('%Y-%m-%d')
        dates.append(date)
        counts.append(date_counts.get(date, 0))
    
    chart_data = {
        'dates': dates,
        'counts': counts,
        'total': sum(counts)  # Add total for template
    }
    
    return render_template('analytics.html',
                         stats=stats,
                         campaigns=campaigns,
                         template_stats=template_stats,
                         recent_activity=recent_activity,
                         chart_data=chart_data)


@app.route("/campaigns")
@login_required
def campaigns_page():
    """View all campaigns"""
    campaigns = db.get_user_campaigns(current_user.id)  # no limit — show everything
    return render_template('campaigns.html', campaigns=campaigns)


@app.route("/campaign/<int:campaign_id>")
@login_required
def campaign_details(campaign_id):
    """View campaign details"""
    campaign = db.get_campaign(campaign_id)
    
    if not campaign or campaign['user_id'] != current_user.id:
        flash("Campaign not found", "error")
        return redirect(url_for('campaigns_page'))
    
    messages = db.get_campaign_messages(campaign_id)
    
    return render_template('campaign_details.html',
                         campaign=campaign,
                         messages=messages)


@app.route("/api/campaigns/<int:campaign_id>/mark-failed", methods=["POST"])
@login_required
def mark_campaign_failed(campaign_id):
    """Force a stuck running campaign to failed status."""
    campaign = db.get_campaign(campaign_id)
    if not campaign or campaign['user_id'] != current_user.id:
        return jsonify({'success': False, 'error': 'Campaign not found'}), 404
    from datetime import datetime as _dt
    db.update_campaign_status(campaign_id, 'failed', completed_at=_dt.now().isoformat())
    return jsonify({'success': True})


@app.route("/api/campaigns/<int:campaign_id>/delete", methods=["POST"])
@login_required
def delete_campaign(campaign_id):
    """Delete a campaign and all its messages."""
    campaign = db.get_campaign(campaign_id)
    if not campaign or campaign['user_id'] != current_user.id:
        return jsonify({'success': False, 'error': 'Campaign not found'}), 404
    if campaign['status'] == 'running':
        return jsonify({'success': False, 'error': 'Cannot delete a campaign that is currently running'}), 400
    db.delete_campaign(campaign_id)
    db.log_activity(
        user_id=current_user.id,
        username=current_user.username,
        action='Campaign Deleted',
        details=f"Deleted campaign: {campaign['campaign_name']} (ID {campaign_id})",
        ip_address=request.remote_addr
    )
    return jsonify({'success': True})


@app.route("/api/campaigns/<int:campaign_id>/resend-unsent", methods=["POST"])
@login_required
def resend_unsent_campaign(campaign_id):
    """Re-queue failed/queued messages in the same campaign."""
    campaign = db.get_campaign(campaign_id)
    if not campaign or campaign['user_id'] != current_user.id:
        return jsonify({'success': False, 'error': 'Campaign not found'}), 404

    unsent = db.get_unsent_campaign_messages(campaign_id)
    if not unsent:
        return jsonify({'success': False, 'error': 'No unsent messages found'})

    import json as _json

    count = db.reset_messages_for_resend(campaign_id)
    queued = 0
    errors = []

    for msg in unsent:
        try:
            phone  = msg['phone_number']
            msg_id = msg['id']

            if msg['template_name']:
                try:
                    params = _json.loads(msg['template_params']) if msg.get('template_params') else []
                except Exception:
                    params = []
                try:
                    btn_p = _json.loads(msg['button_params']) if msg.get('button_params') else None
                except Exception:
                    btn_p = None
                lang = msg.get('template_language') or 'en_US'
                stored_media_id = msg.get('header_media_id') or None
                message_queue.add_message(
                    send_template,
                    phone,
                    msg['template_name'],
                    params,
                    lang,
                    header_media_id=stored_media_id,
                    button_params=btn_p,
                    user_id=current_user.id,
                    username=current_user.username,
                    campaign_id=campaign_id,
                    message_id=msg_id
                )
            else:
                message_queue.add_message(
                    send_text,
                    phone,
                    msg['message_content'] or '',
                    user_id=current_user.id,
                    username=current_user.username,
                    campaign_id=campaign_id,
                    message_id=msg_id
                )
            queued += 1
        except Exception as e:
            logger.error(f"Resend: failed to queue message {msg.get('id')}: {e}")
            errors.append(str(e))

    logger.info(f"Resend: queued {queued}/{count} messages for campaign {campaign_id}")
    return jsonify({'success': True, 'queued': queued, 'errors': errors})


@app.route("/activity-log")
@login_required
def activity_log_page():
    """View activity log"""
    activities = db.get_user_activity(current_user.id, limit=100)
    return render_template('activity_log.html', activities=activities)


# ============================================================
# AUTOMATION SETTINGS
# ============================================================

@app.route("/automation", methods=["GET"])
@login_required
def automation_page():
    """Legacy automation page — redirect to Flows."""
    return redirect(url_for('flows_page'))


# ============================================================
# FLOWS
# ============================================================

def _parse_drawflow_canvas(canvas_data_str):
    """Parse Drawflow.export() JSON into a list of flow_step dicts."""
    try:
        canvas = json.loads(canvas_data_str)
        nodes = canvas['drawflow']['Home']['data']
    except Exception as e:
        raise ValueError(f"Invalid canvas JSON: {e}")

    def first_connection(output_obj):
        if not output_obj:
            return None
        connections = output_obj.get('connections', [])
        return str(connections[0]['node']) if connections else None

    steps = []
    for node_id, node in nodes.items():
        step_type = node.get('name', '')
        config = node.get('data', {})
        outputs = node.get('outputs', {})

        if step_type == 'condition':
            next_yes = first_connection(outputs.get('output_1'))
            next_no = first_connection(outputs.get('output_2'))
        else:
            next_yes = first_connection(outputs.get('output_1'))
            next_no = None

        steps.append({
            'step_key': str(node_id),
            'step_type': step_type,
            'config': config,
            'next_yes': next_yes,
            'next_no': next_no,
        })

    return steps


def _validate_flow_steps(steps):
    """Validate parsed flow steps. Returns (ok, error_message)."""
    triggers = [s for s in steps if s['step_type'] == 'trigger']
    if len(triggers) != 1:
        return False, "Flow must have exactly one Trigger node"
    sends = [s for s in steps if s['step_type'] == 'send_message']
    if not sends:
        return False, "Flow must have at least one Send Message node"
    for s in steps:
        if s['step_type'] == 'condition' and (not s['next_yes'] or not s['next_no']):
            return False, "All Condition nodes must have both Yes and No branches connected"
    # Cycle detection via DFS
    step_map = {s['step_key']: s for s in steps}
    trigger = triggers[0]
    visited, stack = set(), [trigger['step_key']]
    while stack:
        key = stack.pop()
        if key in visited:
            return False, "Flow contains a cycle"
        visited.add(key)
        node = step_map.get(key)
        if node:
            if node.get('next_yes'):
                stack.append(node['next_yes'])
            if node.get('next_no'):
                stack.append(node['next_no'])
    return True, None


def _df_node(node_id, node_type, data, inputs, outputs, pos_x, pos_y):
    """Build a complete Drawflow node dict including all fields Drawflow needs on import."""
    _meta = {
        'trigger':      ('Trigger',      'node-trigger',      'accent-trigger',   'fas fa-bolt',           'icon-trigger'),
        'send_message': ('Send Message', 'node-send_message', 'accent-send',      'fas fa-comment-alt',    'icon-send'),
        'wait':         ('Wait / Delay', 'node-wait',         'accent-wait',      'fas fa-clock',          'icon-wait'),
        'condition':    ('Condition',    'node-condition',     'accent-condition', 'fas fa-code-branch',    'icon-condition'),
        'exit':         ('Exit Flow',    'node-exit',         'accent-exit',      'fas fa-flag-checkered', 'icon-exit'),
    }
    title, css_class, accent, icon, icon_cls = _meta.get(node_type, ('Node','','','fas fa-circle',''))

    # Desc line matching JS nodeDesc()
    if node_type == 'trigger':
        labels = {'order_confirmation':'Order Placed','fulfillment':'Dispatched','abandoned_cart':'Abandoned Cart','manual':'Manual'}
        desc = labels.get(data.get('trigger_type',''), 'Trigger')
    elif node_type == 'send_message':
        desc = data.get('template_name') or 'No template set'
    elif node_type == 'wait':
        desc = f"{data.get('hours',24)}h delay"
    elif node_type == 'condition':
        desc = {'replied_within_X_hours':'Replied within…','read_within_X_hours':'Read within…','placed_order':'Placed order?'}.get(data.get('condition_type',''),'Condition')
    elif node_type == 'exit':
        desc = 'End of journey'
    else:
        desc = node_type

    html = (
        '<div class="df-card">'
        f'<div class="df-card-accent {accent}"></div>'
        '<div class="df-card-body">'
        '<div class="df-card-header">'
        f'<div class="df-card-icon {icon_cls}"><i class="{icon}"></i></div>'
        f'<div class="df-card-title">{title}</div>'
        '</div>'
        f'<div class="df-card-desc">{desc}</div>'
        '</div>'
        '</div>'
    )
    return {
        'id': node_id,
        'name': node_type,
        'data': data,
        'class': css_class,
        'html': html,
        'typenode': False,
        'inputs': inputs,
        'outputs': outputs,
        'pos_x': pos_x,
        'pos_y': pos_y,
    }


def _repair_migrated_canvases(user_id, flows):
    """Fix existing migrated flows whose canvas nodes are missing typenode/html/class fields."""
    for flow in flows:
        canvas_raw = flow.get('canvas_data')
        if not canvas_raw:
            continue
        try:
            canvas = json.loads(canvas_raw)
            nodes = canvas['drawflow']['Home']['data']
        except Exception:
            continue
        needs_repair = any('typenode' not in node for node in nodes.values())
        if not needs_repair:
            continue
        # Rebuild each node with complete fields
        new_nodes = {}
        for key, node in nodes.items():
            node_type = node.get('name', '')
            new_nodes[key] = _df_node(
                node['id'], node_type, node.get('data', {}),
                inputs=node.get('inputs', {}),
                outputs=node.get('outputs', {}),
                pos_x=node.get('pos_x', 100),
                pos_y=node.get('pos_y', 200),
            )
        new_canvas = json.dumps({'drawflow': {'Home': {'data': new_nodes}}})
        db.update_flow(flow['id'], canvas_data=new_canvas)
        logger.info(f"Repaired canvas for flow {flow['id']} ({flow['name']})")


def _maybe_migrate_automation_to_flows(user_id):
    """One-time migration: create default flows from automation_settings if no flows exist yet.
    Also repairs existing migrated flows whose canvas nodes are missing required Drawflow fields."""
    existing = db.get_user_flows(user_id)
    if existing:
        # Repair pass: fix any migrated flows whose canvas nodes lack 'typenode' (old format)
        _repair_migrated_canvases(user_id, existing)
        return
    settings = db.get_automation_settings(user_id)
    trigger_map = {
        'order_confirmation': 'Order Confirmation',
        'fulfillment': 'Order Dispatched',
        'abandoned_cart': 'Abandoned Cart Recovery',
    }
    node_id = 1
    for event_type, flow_name in trigger_map.items():
        s = settings.get(event_type, {})
        template_name = (s.get('template_name') or '').strip()
        if not template_name:
            continue
        delay_hours = int(s.get('delay_hours') or 0)

        nodes = {}

        # Trigger node
        trigger_key = str(node_id)
        nodes[trigger_key] = _df_node(
            node_id, 'trigger', {'trigger_type': event_type},
            inputs={}, outputs={'output_1': {'connections': []}},
            pos_x=100, pos_y=200,
        )
        node_id += 1
        prev_key = trigger_key

        # Optional wait node
        if delay_hours > 0:
            wait_key = str(node_id)
            nodes[wait_key] = _df_node(
                node_id, 'wait', {'hours': delay_hours},
                inputs={'input_1': {'connections': [{'node': prev_key, 'input': 'output_1'}]}},
                outputs={'output_1': {'connections': []}},
                pos_x=350, pos_y=200,
            )
            nodes[prev_key]['outputs']['output_1']['connections'].append({'node': wait_key, 'output': 'input_1'})
            node_id += 1
            prev_key = wait_key

        # Send message node
        msg_key = str(node_id)
        nodes[msg_key] = _df_node(
            node_id, 'send_message',
            {'template_name': template_name, 'template_language': s.get('template_language') or 'en_US', 'param_map': {}},
            inputs={'input_1': {'connections': [{'node': prev_key, 'input': 'output_1'}]}},
            outputs={'output_1': {'connections': []}},
            pos_x=600, pos_y=200,
        )
        nodes[prev_key]['outputs']['output_1']['connections'].append({'node': msg_key, 'output': 'input_1'})
        node_id += 1
        prev_key = msg_key

        # Exit node
        exit_key = str(node_id)
        nodes[exit_key] = _df_node(
            node_id, 'exit', {},
            inputs={'input_1': {'connections': [{'node': prev_key, 'input': 'output_1'}]}},
            outputs={},
            pos_x=850, pos_y=200,
        )
        nodes[prev_key]['outputs']['output_1']['connections'].append({'node': exit_key, 'output': 'input_1'})
        node_id += 1

        canvas_data = json.dumps({'drawflow': {'Home': {'data': nodes}}})
        flow_id = db.create_flow(user_id, flow_name, event_type)
        db.update_flow(flow_id, canvas_data=canvas_data)
        parsed_steps = _parse_drawflow_canvas(canvas_data)
        db.replace_flow_steps(flow_id, parsed_steps)
        if s.get('enabled'):
            db.update_flow(flow_id, status='active')

    logger.info(f"Migrated automation_settings → flows for user {user_id}")


@app.route("/flows")
@login_required
def flows_page():
    _maybe_migrate_automation_to_flows(current_user.id)
    flows = db.get_user_flows(current_user.id)
    for flow in flows:
        counts = db.get_flow_participant_counts(flow['id'])
        flow['active_count'] = counts.get('active', 0)
        flow['completed_count'] = counts.get('completed', 0)
        flow['total_count'] = sum(counts.values())
    custom_segments = db.get_user_segments(current_user.id)
    return render_template('flows.html', flows=flows, custom_segments=custom_segments)


@app.route("/flows/<int:flow_id>")
@login_required
def flow_editor_page(flow_id):
    try:
        flow = db.get_flow(flow_id)
        if not flow or str(flow['user_id']) != str(current_user.id):
            flash("Flow not found", "error")
            return redirect(url_for('flows_page'))
        steps = db.get_flow_steps(flow_id)
        try:
            wa_templates = [t for t in get_templates(WABA_ID) if t.get('status') == 'APPROVED']
        except Exception:
            wa_templates = []
        return render_template('flow_editor.html', flow=flow, steps=steps, wa_templates=wa_templates)
    except Exception as e:
        logger.error(f"Flow editor error for flow {flow_id}: {e}", exc_info=True)
        flash(f"Error loading flow editor: {e}", "error")
        return redirect(url_for('flows_page'))


@app.route("/api/flows", methods=["POST"])
@login_required
def api_create_flow():
    data = request.json or {}
    name = (data.get('name') or '').strip()
    trigger_type = (data.get('trigger_type') or '').strip()
    if not name or not trigger_type:
        return jsonify({'success': False, 'error': 'name and trigger_type required'}), 400
    flow_id = db.create_flow(current_user.id, name, trigger_type)
    return jsonify({'success': True, 'flow_id': flow_id})


@app.route("/api/flows/<int:flow_id>/save", methods=["POST"])
@login_required
def api_save_flow(flow_id):
    flow = db.get_flow(flow_id)
    if not flow or flow['user_id'] != current_user.id:
        return jsonify({'success': False, 'error': 'Not found'}), 404
    data = request.json or {}
    canvas_data = data.get('canvas_data', '')
    name = (data.get('name') or '').strip()
    try:
        steps = _parse_drawflow_canvas(canvas_data)
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    ok, err = _validate_flow_steps(steps)
    if not ok:
        return jsonify({'success': False, 'error': err}), 400
    db.update_flow(flow_id, name=name or None, canvas_data=canvas_data)
    db.replace_flow_steps(flow_id, steps)
    return jsonify({'success': True})


@app.route("/api/flows/<int:flow_id>/settings", methods=["POST"])
@login_required
def api_flow_settings(flow_id):
    flow = db.get_flow(flow_id)
    if not flow or str(flow['user_id']) != str(current_user.id):
        return jsonify({'success': False, 'error': 'Not found'}), 404
    data = request.json or {}
    if 'allow_reenroll' not in data:
        return jsonify({'success': False, 'error': 'allow_reenroll required'}), 400
    db.update_flow(flow_id, allow_reenroll=bool(data.get('allow_reenroll')))
    return jsonify({'success': True})


@app.route("/api/flows/<int:flow_id>/activate", methods=["POST"])
@login_required
def api_activate_flow(flow_id):
    flow = db.get_flow(flow_id)
    if not flow or flow['user_id'] != current_user.id:
        return jsonify({'success': False, 'error': 'Not found'}), 404
    steps = db.get_flow_steps(flow_id)
    if not steps:
        return jsonify({'success': False, 'error': 'Save the flow before activating'}), 400
    ok, err = _validate_flow_steps([{'step_key': s['step_key'], 'step_type': s['step_type'],
                                      'next_yes': s['next_yes'], 'next_no': s['next_no'],
                                      'config': json.loads(s['config'] or '{}')} for s in steps])
    if not ok:
        return jsonify({'success': False, 'error': err}), 400
    db.update_flow(flow_id, status='active')
    return jsonify({'success': True})


@app.route("/api/flows/<int:flow_id>/pause", methods=["POST"])
@login_required
def api_pause_flow(flow_id):
    flow = db.get_flow(flow_id)
    if not flow or flow['user_id'] != current_user.id:
        return jsonify({'success': False, 'error': 'Not found'}), 404
    db.update_flow(flow_id, status='paused')
    return jsonify({'success': True})


@app.route("/api/flows/<int:flow_id>", methods=["DELETE"])
@login_required
def api_delete_flow(flow_id):
    flow = db.get_flow(flow_id)
    if not flow or flow['user_id'] != current_user.id:
        return jsonify({'success': False, 'error': 'Not found'}), 404
    db.delete_flow(flow_id)
    return jsonify({'success': True})


@app.route("/api/flows/<int:flow_id>/stats")
@login_required
def api_flow_stats(flow_id):
    flow = db.get_flow(flow_id)
    if not flow or str(flow['user_id']) != str(current_user.id):
        return jsonify({'success': False, 'error': 'Not found'}), 404
    steps = db.get_flow_step_stats(flow_id)
    return jsonify({'success': True, 'steps': steps})


@app.route("/api/flows/<int:flow_id>/participants")
@login_required
def api_flow_participants(flow_id):
    flow = db.get_flow(flow_id)
    if not flow or flow['user_id'] != current_user.id:
        return jsonify({'success': False, 'error': 'Not found'}), 404
    participants = db.get_flow_participants(flow_id)
    counts = db.get_flow_participant_counts(flow_id)
    return jsonify({'success': True, 'participants': participants, 'counts': counts})


@app.route("/api/flows/<int:flow_id>/enroll", methods=["POST"])
@login_required
def api_enroll_flow(flow_id):
    flow = db.get_flow(flow_id)
    if not flow or flow['user_id'] != current_user.id:
        return jsonify({'success': False, 'error': 'Not found'}), 404
    if flow['status'] != 'active':
        return jsonify({'success': False, 'error': 'Flow must be active to enroll customers'}), 400
    data = request.json or {}
    segment_type = (data.get('segment_type') or '').strip()
    raw_phones = data.get('phone_numbers') or []   # list of raw strings from the textarea

    first_step = get_flow_first_step_key(db, flow_id)
    if not first_step:
        return jsonify({'success': False, 'error': 'Flow has no steps — save the flow first'}), 400

    if not segment_type and not raw_phones:
        return jsonify({'success': False, 'error': 'Choose a segment or enter at least one phone number'}), 400

    # Collect customers from segment
    segment_customers = []
    if segment_type:
        if segment_type.startswith('custom_'):
            try:
                seg_id = int(segment_type.split('_', 1)[1])
                seg = db.get_segment_by_id(seg_id)
                conditions = json.loads(seg['conditions'] or '{}') if seg else {}
                segment_customers = db.get_all_customers(current_user.id, conditions)
            except Exception:
                segment_customers = []
        else:
            segment_customers = db.get_segment_customers(current_user.id, segment_type)

    # Build phone → context map from segment (preserves first_name/email)
    phone_ctx = {}
    for c in segment_customers:
        phone = c.get('phone')
        if phone:
            phone_ctx[phone] = {
                'first_name': c.get('first_name') or (c.get('email', '').split('@')[0]),
            }

    # Add manually entered phone numbers (normalize, look up customer if exists)
    for raw in raw_phones:
        raw = raw.strip()
        if not raw:
            continue
        normalized = _normalize_phone_webhook(raw)
        if normalized and normalized not in phone_ctx:
            customer = db.get_customer_by_phone(normalized)
            if customer:
                ctx = {'first_name': customer.get('first_name') or (customer.get('email', '').split('@')[0])}
            else:
                ctx = {'first_name': ''}
            phone_ctx[normalized] = ctx

    enrolled, skipped = 0, 0
    for phone, ctx in phone_ctx.items():
        pid = flow_enroll_participant(db, flow_id, phone, ctx, first_step)
        if pid:
            enrolled += 1
        else:
            skipped += 1
    return jsonify({'success': True, 'enrolled': enrolled, 'skipped': skipped})


@app.route("/api/automation-settings", methods=["POST"])
@login_required
def save_automation_settings():
    """Save automation settings (JSON body)."""
    try:
        data = request.json or {}

        for event_type in ['order_confirmation', 'fulfillment', 'abandoned_cart']:
            block = data.get(event_type, {})
            extra_data = {}
            if event_type == 'abandoned_cart':
                extra_data = {}
            db.save_automation_setting(
                user_id=current_user.id,
                event_type=event_type,
                enabled=int(bool(block.get('enabled'))),
                template_name=(block.get('template_name') or '').strip(),
                template_language=(block.get('template_language') or 'en_US').strip(),
                delay_hours=int(block.get('delay_hours') or
                                (1 if event_type == 'abandoned_cart' else 0)),
                extra_data=extra_data,
            )

        db.log_activity(
            user_id=current_user.id,
            username=current_user.username,
            action='Automation Settings Saved',
            details='Updated automation webhook settings',
            ip_address=request.remote_addr
        )
        return jsonify({'success': True, 'message': 'Settings saved successfully'})

    except Exception as e:
        logger.error(f"❌ Error saving automation settings: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================
# ORDER TRACKING REDIRECT (public — no login required)
# ============================================================

@app.route("/track/<order_ref>")
def track_order(order_ref):
    """Public interstitial: /track/<order_number> → shows branded page → courier tracking URL."""
    tracking_number = None
    tracking_company = None
    status_url = None
    try:
        result = db.get_order_tracking_url(order_ref)
        if result:
            destination = result['tracking_url'] or ''
            order_number = result['order_number'] or order_ref
            tracking_number = result.get('tracking_number')
            tracking_company = result.get('tracking_company')
            status_url = result.get('order_status_url')

            # Self-heal: orders fulfilled before order_status_url was stored have
            # none — fetch it once from Shopify and cache it for next time.
            if not status_url:
                status_url = _fetch_order_status_url(result.get('shopify_order_id'))
                if status_url:
                    try:
                        db.save_order_status_url(result['shopify_order_id'], status_url)
                    except Exception as e:
                        logger.warning(f"Could not cache backfilled order_status_url: {e}")
        else:
            destination = ''
            order_number = order_ref
    except Exception as e:
        logger.error(f"❌ /track/{order_ref} error: {e}")
        destination = ''
        order_number = order_ref

    # Courier name is display-only. We never link to a courier site directly:
    # DTDC (and others) serve a WAF block page for deep links arriving from an
    # external site / in-app browser, which reads as a scam to the customer.
    courier_map = {
        'dtdc':            'DTDC',
        'delhivery':       'Delhivery',
        'fedex':           'FedEx',
        'bluedart':        'BlueDart',
        'ecomexpress':     'Ecom Express',
        'xpressbees':      'XpressBees',
        'shiprocket':      'Shiprocket',
        'ekart':           'Ekart',
        'shadowfax':       'Shadowfax',
        'amazonlogistics': 'Amazon Logistics',
    }
    courier_name = (tracking_company or '').strip() or 'our courier partner'
    haystack = f"{destination} {tracking_company or ''}".lower().replace(' ', '').replace('-', '')
    for key, name in courier_map.items():
        if key in haystack:
            courier_name = name
            break

    # AWB: prefer the stored value, else recover it from the courier tracking URL
    if not tracking_number:
        try:
            qs = parse_qs(urlparse(destination).query)
            for k in ('awb', 'AWB', 'awb_no', 'trackingnumber', 'tracking_number',
                      'trackingNo', 'ref', 'id'):
                if qs.get(k):
                    tracking_number = qs[k][0]
                    break
        except Exception:
            pass

    # Primary destination is Shopify's own customer-facing order page (on boxbox.in,
    # carries its own auth key). Orders predating this column have none stored — those
    # fall back to the copyable AWB rather than a courier link that may block.
    primary_url = status_url or ''
    logger.info(f"🔗 Tracking page: /track/{order_ref} → "
                f"{primary_url or '(no link, AWB only)'} (awb={tracking_number})")

    # Format order number for display
    order_number_str = str(order_number).lstrip('#')
    display_order = f"#F1{order_number_str}"

    # Optional blocks — only rendered when we actually have the data
    awb_block = ""
    if tracking_number:
        awb_block = f"""
      <div class="awb-label">Tracking number</div>
      <div class="awb-row">
        <span class="awb" id="awb">{tracking_number}</span>
        <button class="copy" onclick="copyAwb()" aria-label="Copy tracking number">Copy</button>
      </div>"""

    if primary_url:
        cta_block = f"""
      <a class="btn" href="{primary_url}">Track My Order &rarr;</a>"""
    elif tracking_number:
        cta_block = f"""
      <p class="hint">Use the tracking number above on
        <span style="font-weight:600;">{courier_name}</span>'s website to see live status.</p>"""
    else:
        cta_block = """
      <a class="btn" href="https://boxbox.in">Visit boxbox.in &rarr;</a>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="referrer" content="no-referrer">
  <title>Track Your Order — boxbox</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, sans-serif;
      background: #f9f7f4;
      color: #1a1a1a;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 24px;
    }}
    .wrapper {{
      width: 100%;
      max-width: 420px;
      text-align: center;
    }}
    .logo {{
      display: block;
      margin-bottom: 16px;
      text-decoration: none;
    }}
    .logo img {{
      height: 250px;
      width: auto;
      margin-top: -60px;
      margin-bottom: -60px;
    }}
    .card {{
      background: #fff;
      border-radius: 20px;
      padding: 40px 32px;
      box-shadow: 0 2px 24px rgba(0,0,0,0.07);
    }}
    .icon-wrap {{
      width: 72px;
      height: 72px;
      background: #f0f7f0;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0 auto 24px;
      font-size: 32px;
    }}
    h1 {{
      font-size: 20px;
      font-weight: 700;
      color: #1a1a1a;
      margin-bottom: 10px;
      line-height: 1.3;
    }}
    .order-tag {{
      display: inline-block;
      background: #f0f7f0;
      color: #2d7a2d;
      font-size: 13px;
      font-weight: 600;
      padding: 5px 14px;
      border-radius: 20px;
      margin-bottom: 16px;
    }}
    .sub {{
      font-size: 14px;
      color: #666;
      margin-bottom: 28px;
      line-height: 1.6;
    }}
    .btn {{
      display: block;
      background: #1a1a1a;
      color: #fff;
      font-weight: 700;
      font-size: 15px;
      padding: 16px 24px;
      border-radius: 12px;
      text-decoration: none;
      letter-spacing: 0.3px;
      transition: opacity 0.2s;
    }}
    .btn:hover {{ opacity: 0.85; }}
    .hint {{
      font-size: 13px;
      color: #666;
      line-height: 1.6;
      background: #f7f7f5;
      border-radius: 12px;
      padding: 14px 16px;
    }}
    .awb-label {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: #999;
      margin-bottom: 8px;
    }}
    .awb-row {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      background: #f7f7f5;
      border: 1px dashed #ddd;
      border-radius: 12px;
      padding: 12px 14px;
      margin-bottom: 24px;
    }}
    .awb {{
      font-family: 'SF Mono', Menlo, Consolas, monospace;
      font-size: 15px;
      font-weight: 700;
      letter-spacing: 0.5px;
      color: #1a1a1a;
      word-break: break-all;
      text-align: left;
    }}
    .copy {{
      flex-shrink: 0;
      background: #1a1a1a;
      color: #fff;
      border: none;
      border-radius: 8px;
      padding: 8px 14px;
      font-size: 12px;
      font-weight: 700;
      cursor: pointer;
      font-family: inherit;
    }}
    .courier-tag {{
      font-size: 12px;
      color: #999;
      margin-top: 18px;
    }}
    .courier-tag span {{ color: #1a1a1a; font-weight: 600; }}
    .footer {{
      margin-top: 32px;
      font-size: 12px;
      color: #aaa;
      line-height: 1.6;
    }}
    .footer a {{ color: #aaa; text-decoration: none; }}
  </style>
</head>
<body>
  <div class="wrapper">
    <a class="logo" href="https://boxbox.in"><img src="/static/boxbox-logo.png" alt="boxbox"></a>
    <div class="card">
      <div class="icon-wrap">🚚</div>
      <div class="order-tag">Order {display_order}</div>
      <h1>Your order is on its way!</h1>
      <p class="sub">Your parcel has been picked up by <span style="font-weight:600;">{courier_name}</span>.</p>
      {awb_block}
      {cta_block}
      <div class="courier-tag">Shipped via <span>{courier_name}</span></div>
    </div>
    <div class="footer">
      Questions? <a href="https://boxbox.in">Visit boxbox.in</a> or reply to your WhatsApp message.
    </div>
  </div>
  <script>
    function copyAwb() {{
      var el = document.getElementById('awb');
      if (!el) return;
      var text = el.innerText.trim();
      var btn = document.querySelector('.copy');
      function done() {{
        if (!btn) return;
        var old = btn.innerText;
        btn.innerText = 'Copied';
        setTimeout(function () {{ btn.innerText = old; }}, 1500);
      }}
      if (navigator.clipboard && navigator.clipboard.writeText) {{
        navigator.clipboard.writeText(text).then(done).catch(fallback);
      }} else {{
        fallback();
      }}
      function fallback() {{
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        try {{ document.execCommand('copy'); done(); }} catch (e) {{}}
        document.body.removeChild(ta);
      }}
    }}
  </script>
</body>
</html>"""
    return html, 200


# ============================================================
# TWO-WAY INBOX
# ============================================================

def _inbox_within_24h_window(user_id, phone):
    """WhatsApp only allows free-form (non-template) replies within 24h of the
    customer's last inbound message. Returns (within_window, last_inbound_at)."""
    last_inbound = db.get_last_inbound_message_at(user_id, phone)
    if not last_inbound:
        return False, None
    try:
        last_dt = datetime.fromisoformat(last_inbound)
    except Exception:
        return False, last_inbound
    return (datetime.now() - last_dt) < timedelta(hours=24), last_inbound


@app.route("/inbox")
@login_required
def inbox_page():
    conversations = db.get_inbox_conversations(current_user.id)
    return render_template('inbox.html', conversations=conversations)


@app.route("/inbox/<path:phone>")
@login_required
def inbox_thread_page(phone):
    if not phone.startswith('+'):
        phone = '+' + phone
    thread = db.get_inbox_thread(current_user.id, phone)
    within_window, last_inbound_at = _inbox_within_24h_window(current_user.id, phone)
    customer = db.get_customer_by_phone(phone)
    db.mark_inbox_thread_read(current_user.id, phone)
    return render_template(
        'inbox_thread.html',
        phone=phone, thread=thread, customer=customer,
        within_window=within_window, last_inbound_at=last_inbound_at
    )


@app.route("/api/inbox/send", methods=["POST"])
@login_required
def api_inbox_send():
    data = request.json or {}
    phone = (data.get('phone') or '').strip()
    message = (data.get('message') or '').strip()
    if not phone or not message:
        return jsonify({'success': False, 'error': 'phone and message required'}), 400

    within_window, _ = _inbox_within_24h_window(current_user.id, phone)
    if not within_window:
        return jsonify({
            'success': False,
            'error': 'outside_24h_window',
            'message': "This customer hasn't messaged in the last 24 hours. WhatsApp only allows "
                       "free-form replies within 24h of their last message — send a template message instead."
        }), 409

    status_code, response = send_text(phone, message)
    if status_code not in (200, 201):
        err = None
        if isinstance(response, dict):
            err_obj = response.get('error')
            err = err_obj.get('message') if isinstance(err_obj, dict) else err_obj
        return jsonify({'success': False, 'error': err or f'Send failed ({status_code})'}), 502

    wamid = None
    if isinstance(response, dict):
        msgs = response.get('messages', [])
        wamid = msgs[0].get('id') if msgs else None

    db.add_inbox_message(
        user_id=current_user.id, phone=phone, direction='outbound',
        message_text=message, message_type='text',
        whatsapp_message_id=wamid, status='sent'
    )
    return jsonify({'success': True})


# ============================================================
# SHOPIFY & CUSTOMER MANAGEMENT
# ============================================================

@app.route("/customers")
@login_required
def customers_page():
    """View all customers with filtering"""
    segment_filter = request.args.get('segment', None)
    
    # Get filter parameters from query string
    min_order_value = request.args.get('min_order_value', type=float)
    max_order_value = request.args.get('max_order_value', type=float)
    min_orders = request.args.get('min_orders', type=int)
    max_orders = request.args.get('max_orders', type=int)
    
    filters = {}
    if segment_filter:
        filters['segment_type'] = segment_filter
    if min_order_value is not None:
        filters['min_order_value'] = min_order_value
    if max_order_value is not None:
        filters['max_order_value'] = max_order_value
    if min_orders is not None:
        filters['min_orders'] = min_orders
    if max_orders is not None:
        filters['max_orders'] = max_orders
    
    customers = db.get_all_customers(current_user.id, filters)
    custom_segments = db.get_user_segments(current_user.id)
    
    # Auto-generate default segments
    default_segments = [
        {'name': 'All Customers', 'type': 'all', 'count': len(db.get_all_customers(current_user.id))},
        {'name': 'Has Phone Number', 'type': 'has_phone', 'count': len(db.get_all_customers(current_user.id, {'has_phone': True}))},
        {'name': 'Engaged (Last 7 Days)', 'type': 'engaged_last_7_days', 'count': len(db.get_segment_customers(current_user.id, 'engaged_last_7_days'))},
        {'name': 'Not Engaged (Last 7 Days)', 'type': 'not_engaged_last_7_days', 'count': len(db.get_segment_customers(current_user.id, 'not_engaged_last_7_days'))},
        {'name': 'Never Messaged', 'type': 'no_message_sent', 'count': len(db.get_segment_customers(current_user.id, 'no_message_sent'))},
        {'name': 'High Value (>$1000)', 'type': 'high_value', 'count': len(db.get_segment_customers(current_user.id, 'high_value'))},
        {'name': 'Has Orders', 'type': 'has_orders', 'count': len(db.get_segment_customers(current_user.id, 'has_orders'))},
        {'name': 'Replied to Messages', 'type': 'replied', 'count': len(db.get_segment_customers(current_user.id, 'replied'))},
    ]
    
    # Add custom segments with their counts
    for segment in custom_segments:
        segment['type'] = f"custom_{segment['id']}"
        segment['name'] = segment['segment_name']
        segment['count'] = len(db.get_segment_customers(current_user.id, segment['type']))
        default_segments.append(segment)
    
    return render_template('customers.html', 
                         customers=customers, 
                         segments=default_segments,
                         custom_segments=custom_segments,
                         current_segment=segment_filter,
                         filters=filters)


@app.route("/api/sync-shopify", methods=["POST"])
@login_required
def sync_shopify():
    """Sync customers from Shopify"""
    try:
        from utils.shopify_integration import ShopifyIntegration
        import config
        
        logger.info(f"🔄 Starting Shopify sync for user {current_user.username}")
        
        if not config.SHOPIFY_SHOP_NAME or not config.SHOPIFY_ACCESS_TOKEN:
            logger.error("❌ Shopify credentials not configured")
            return jsonify({
                'success': False,
                'error': 'Shopify credentials not configured. Please add SHOPIFY_SHOP_NAME and SHOPIFY_ACCESS_TOKEN to your .env file'
            })
        
        logger.info(f"✅ Shopify credentials found - Shop: {config.SHOPIFY_SHOP_NAME}")
        
        shopify = ShopifyIntegration(config.SHOPIFY_SHOP_NAME, config.SHOPIFY_ACCESS_TOKEN)

        last_sync_date = db.get_last_shopify_created_at(current_user.id)
        if last_sync_date:
            logger.info(f"🔄 Incremental sync: fetching customers created after {last_sync_date}")
        else:
            logger.info("🔄 Full sync: no previous customers found, fetching all")

        customers = shopify.fetch_customers(created_at_min=last_sync_date)

        logger.info(f"📊 Fetched {len(customers)} customers from Shopify")
        
        parsed = [shopify.parse_customer_data(c) for c in customers]
        to_sync = [c for c in parsed if c['phone']]
        skipped_count = len(parsed) - len(to_sync)
        synced_count = len(to_sync)

        db.bulk_add_or_update_customers(current_user.id, to_sync)

        logger.info(f"📊 Sync complete - Synced: {synced_count}, Skipped (no phone): {skipped_count}")

        db.log_activity(
            user_id=current_user.id,
            username=current_user.username,
            action='Shopify Sync',
            details=f'Synced {synced_count} customers from Shopify (Skipped {skipped_count} without phone numbers)',
            ip_address=request.remote_addr
        )

        if last_sync_date:
            message = f'Incremental sync complete: {synced_count} new customers added'
        else:
            message = f'Full sync complete: {synced_count} customers synced'
        if skipped_count > 0:
            message += f' ({skipped_count} skipped - no phone number)'

        return jsonify({
            'success': True,
            'message': message,
            'synced_count': synced_count,
            'skipped_count': skipped_count,
            'total_fetched': len(customers)
        })
        
    except Exception as e:
        logger.error(f"❌ Error syncing Shopify customers: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route("/api/customers/<segment>")
@login_required
def api_get_customers(segment):
    """API endpoint to get customers by segment"""
    try:
        if segment == 'all':
            customers = db.get_all_customers(current_user.id)
        elif segment.startswith('custom_'):
            try:
                seg_id = int(segment.split('_', 1)[1])
                seg = db.get_segment_by_id(seg_id)
                conditions = json.loads(seg['conditions'] or '{}') if seg else {}
                customers = db.get_all_customers(current_user.id, conditions)
            except Exception:
                customers = []
        else:
            customers = db.get_segment_customers(current_user.id, segment)

        return jsonify({
            'success': True,
            'customers': customers,
            'count': len(customers)
        })
    except Exception as e:
        logger.error(f"Error fetching customers: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route("/api/segments/create", methods=["POST"])
@login_required
def create_custom_segment():
    """Create a custom customer segment"""
    try:
        data = request.json
        segment_name = data.get('segment_name', '').strip()
        
        if not segment_name:
            return jsonify({'success': False, 'error': 'Segment name is required'})
        
        conditions = {
            'min_order_value': data.get('min_order_value'),
            'max_order_value': data.get('max_order_value'),
            'min_orders': data.get('min_orders'),
            'max_orders': data.get('max_orders'),
        }
        
        # Remove None values
        conditions = {k: v for k, v in conditions.items() if v is not None}
        
        segment_id = db.create_segment(
            user_id=current_user.id,
            segment_name=segment_name,
            segment_type='custom',
            conditions=conditions
        )
        
        db.log_activity(
            user_id=current_user.id,
            username=current_user.username,
            action='Create Segment',
            details=f'Created custom segment: {segment_name}',
            ip_address=request.remote_addr
        )
        
        return jsonify({
            'success': True,
            'message': f'Segment "{segment_name}" created successfully',
            'segment_id': segment_id
        })
        
    except Exception as e:
        logger.error(f"Error creating segment: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route("/api/segments/<int:segment_id>/delete", methods=["DELETE"])
@login_required
def delete_custom_segment(segment_id):
    """Delete a custom segment"""
    try:
        success = db.delete_segment(segment_id, current_user.id)
        
        if success:
            db.log_activity(
                user_id=current_user.id,
                username=current_user.username,
                action='Delete Segment',
                details=f'Deleted segment ID: {segment_id}',
                ip_address=request.remote_addr
            )
            return jsonify({'success': True, 'message': 'Segment deleted successfully'})
        else:
            return jsonify({'success': False, 'error': 'Segment not found or unauthorized'})
            
    except Exception as e:
        logger.error(f"Error deleting segment: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route("/api/dashboard-stats")
@login_required
def api_dashboard_stats():
    """API endpoint for dashboard statistics"""
    stats = db.get_dashboard_stats(user_id=current_user.id)
    return jsonify(stats)


@app.route("/api/worker-debug")
@login_required
def worker_debug():
    """Show live stack traces of all threads — use when queue is stuck."""
    import sys, traceback
    frames = sys._current_frames()
    traces = {}
    for thread in threading.enumerate():
        frame = frames.get(thread.ident)
        if frame:
            traces[thread.name] = ''.join(traceback.format_stack(frame))
    return jsonify({
        'workers': [{'name': w.name, 'alive': w.is_alive()} for w in message_queue.workers],
        'thread_traces': traces
    })


@app.route("/queue-status")
@login_required
def queue_status():
    """Get current queue status"""
    try:
        queue_size = message_queue.queue.qsize()
        stats = message_queue.get_stats()
        
        # Calculate rate limit in messages per minute
        rate_per_minute = int((MAX_REQUESTS / TIME_WINDOW) * 60)
        
        return jsonify({
            'queue_size': queue_size,
            'rate_limit': rate_per_minute,
            'total_processed': stats.get('total', 0),
            'successful': stats.get('successful', 0),
            'failed': stats.get('failed', 0),
            'pending': stats.get('pending', 0),
            'workers_alive': stats.get('workers_alive', 0),
            'workers_total': stats.get('workers_total', 0),
            'current_batch': []
        })
    except Exception as e:
        logger.error(f"Error getting queue status: {e}")
        return jsonify({
            'queue_size': 0,
            'rate_limit': 15,
            'current_batch': [],
            'error': str(e)
        })


# ============================================================
# WHATSAPP WEBHOOK FOR STATUS UPDATES
# ============================================================

@app.route("/webhook", methods=["GET", "POST"])
def whatsapp_webhook():
    """
    Webhook endpoint for WhatsApp Business API
    Receives message status updates (delivered, read, etc.)
    """
    if request.method == "GET":
        # Webhook verification
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        
        # Verify token (set this in your .env as WEBHOOK_VERIFY_TOKEN)
        verify_token = os.getenv("WEBHOOK_VERIFY_TOKEN", "your_verify_token_here")
        
        if mode == "subscribe" and token == verify_token:
            logger.info("✅ Webhook verified")
            return challenge, 200
        else:
            logger.warning("❌ Webhook verification failed")
            return "Forbidden", 403
    
    elif request.method == "POST":
        # Handle incoming webhook data
        try:
            data = request.json
            logger.info(f"📥 Webhook received: {data}")
            
            # Process status updates
            if data.get("entry"):
                for entry in data["entry"]:
                    if entry.get("changes"):
                        for change in entry["changes"]:
                            # Handle status updates (delivered, read, failed)
                            if change.get("value") and change["value"].get("statuses"):
                                logger.info(f"📊 Processing {len(change['value']['statuses'])} status updates")
                                for status in change["value"]["statuses"]:
                                    process_message_status(status)
                            
                            # Handle incoming messages (for replies)
                            if change.get("value") and change["value"].get("messages"):
                                logger.info(f"📨 Processing {len(change['value']['messages'])} incoming messages")
                                for message in change["value"]["messages"]:
                                    process_incoming_message(message)
            
            return jsonify({"status": "ok"}), 200
        
        except Exception as e:
            logger.error(f"❌ Webhook error: {e}")
            return jsonify({"error": str(e)}), 500


def process_message_status(status_data):
    """Process message status update from WhatsApp"""
    try:
        message_id = status_data.get("id")
        status = status_data.get("status")  # sent, delivered, read, failed
        timestamp = status_data.get("timestamp")
        recipient_id = status_data.get("recipient_id")
        
        logger.info(f"📊 Status update: {message_id} -> {status}")
        
        if status == "delivered":
            logger.info(f"🚀 Processing delivered status for message: {message_id}")
            db.update_message_engagement(message_id, "delivered", timestamp)
            if recipient_id:
                db.update_customer_message_stats(recipient_id, "sent")
            trigger_immediate_recheck(db, message_id, 'delivered_at', timestamp or datetime.now().isoformat())
            logger.info(f"✅ Delivered status processed")
        elif status == "read":
            logger.info(f"👁️ Processing read status for message: {message_id}")
            db.update_message_engagement(message_id, "read", timestamp)
            if recipient_id:
                db.update_customer_message_stats(recipient_id, "read")
            trigger_immediate_recheck(db, message_id, 'read_at', timestamp or datetime.now().isoformat())
            logger.info(f"✅ Read status processed")
        elif status == "failed":
            error = status_data.get("errors", [{}])[0]
            error_code = error.get("code", 0)
            error_message = error.get("message", "Unknown error")
            logger.error(f"❌ Message {message_id} failed: {error_message} (code: {error_code})")
            db.fail_message_by_whatsapp_id(message_id, error_code, error_message)
    
    except Exception as e:
        logger.error(f"❌ Error processing status: {e}", exc_info=True)


def process_incoming_message(message_data):
    """Process incoming message (reply) from WhatsApp"""
    try:
        from_number = message_data.get("from")
        message_type = message_data.get("type")
        timestamp = message_data.get("timestamp")
        message_id = message_data.get("id")
        
        logger.info(f"📨 Incoming message from {from_number}, type: {message_type}, id: {message_id}")
        
        # Log full message data for debugging
        logger.info(f"🔍 Full message data: {message_data}")
        
        # Extract reply text based on message type
        reply_text = None
        if message_type == "text":
            reply_text = message_data.get("text", {}).get("body", "")
        elif message_type == "image":
            reply_text = "[Image]"
        elif message_type == "video":
            reply_text = "[Video]"
        elif message_type == "audio":
            reply_text = "[Audio]"
        elif message_type == "document":
            reply_text = "[Document]"
        elif message_type == "button":
            reply_text = message_data.get("button", {}).get("text", "[Button Click]")
        
        logger.info(f"💬 Reply text: {reply_text}")

        # Log to the two-way inbox — captures every incoming message (not just the
        # first reply to a given outbound campaign message, which is all
        # update_message_engagement below can record).
        try:
            inbox_user_id = _get_webhook_user_id()
            if inbox_user_id and from_number:
                db.add_inbox_message(
                    user_id=inbox_user_id,
                    phone=_normalize_phone_webhook(from_number),
                    direction='inbound',
                    message_text=reply_text if reply_text is not None else f'[{message_type or "unsupported"} message]',
                    message_type=message_type,
                    whatsapp_message_id=message_id,
                )
        except Exception as e:
            logger.error(f"Inbox logging failed for incoming message: {e}", exc_info=True)

        # Check if this is a reply to our message (has context)
        context = message_data.get("context")
        if context and context.get("id"):
            original_message_id = context["id"]
            logger.info(f"💬 Reply with context to message: {original_message_id}")
            db.update_message_engagement(original_message_id, "replied", timestamp, reply_text)
            trigger_immediate_recheck(db, original_message_id, 'replied_at', timestamp or datetime.now().isoformat())
            logger.info(f"✅ Reply tracking updated for: {original_message_id}")
        else:
            # No context - it's a regular message, try to match by phone number
            logger.info(f"💬 Reply without context from {from_number}")
            # Find most recent sent message to this number
            from utils.database import Database
            import sqlite3
            
            temp_db = Database()
            
            # Use context manager properly
            with temp_db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Remove country code variations for matching
                phone_clean = from_number.replace('+', '').replace('-', '').replace(' ', '')
                
                cursor.execute('''
                    SELECT id, whatsapp_message_id FROM messages
                    WHERE phone_number LIKE ? 
                    AND replied_at IS NULL
                    AND sent_at > datetime('now', '-24 hours')
                    ORDER BY sent_at DESC
                    LIMIT 1
                ''', (f'%{phone_clean[-10:]}',))  # Match last 10 digits
                
                result = cursor.fetchone()
                if result:
                    msg_id = result['whatsapp_message_id'] if result['whatsapp_message_id'] else None
                    if msg_id:
                        db.update_message_engagement(msg_id, "replied", timestamp, reply_text)
                        db.update_customer_message_stats(from_number, "replied")
                        logger.info(f"✅ Reply matched to message ID: {msg_id}")
                    else:
                        logger.warning(f"⚠️ Found message but no WhatsApp ID")
                else:
                    logger.warning(f"⚠️ No recent message found for {from_number}")
        
        # Track button clicks - check multiple button types
        if message_type == "button":
            logger.info(f"🖱️ Button click detected!")
            logger.info(f"🔍 Button data: {message_data.get('button', {})}")
            
            if context and context.get("id"):
                original_message_id = context["id"]
                logger.info(f"✅ Button click has context: {original_message_id}")
                db.update_message_engagement(original_message_id, "clicked", timestamp)
                logger.info(f"✅ Click tracking updated for: {original_message_id}")
            else:
                logger.warning(f"⚠️ Button click without context - trying phone match")
                # Try phone number matching for button clicks too
                from utils.database import Database
                import sqlite3
                
                temp_db = Database()
                
                with temp_db.get_connection() as conn:
                    cursor = conn.cursor()
                    phone_clean = from_number.replace('+', '').replace('-', '').replace(' ', '')
                    
                    cursor.execute('''
                        SELECT id, whatsapp_message_id FROM messages
                        WHERE phone_number LIKE ? 
                        AND clicked_at IS NULL
                        AND sent_at > datetime('now', '-24 hours')
                        ORDER BY sent_at DESC
                        LIMIT 1
                    ''', (f'%{phone_clean[-10:]}',))
                    
                    result = cursor.fetchone()
                    if result:
                        msg_id = result['whatsapp_message_id'] if result['whatsapp_message_id'] else None
                        if msg_id:
                            db.update_message_engagement(msg_id, "clicked", timestamp)
                            logger.info(f"✅ Click matched to message ID: {msg_id}")
                        else:
                            logger.warning(f"⚠️ Found message but no WhatsApp ID")
                    else:
                        logger.warning(f"⚠️ No recent message found for button click")
        
        # Also check for interactive message types
        elif message_type == "interactive":
            logger.info(f"🖱️ Interactive message detected!")
            logger.info(f"🔍 Interactive data: {message_data.get('interactive', {})}")
            
            if context and context.get("id"):
                original_message_id = context["id"]
                db.update_message_engagement(original_message_id, "clicked", timestamp)
                logger.info(f"✅ Interactive click tracking updated for: {original_message_id}")
            else:
                logger.warning(f"⚠️ Interactive message without context")
    
    except Exception as e:
        logger.error(f"❌ Error processing incoming message: {e}", exc_info=True)


# ============================================================
# SHOPIFY WEBHOOKS FOR CART ABANDONMENT & ORDER CONFIRMATION
# ============================================================

@app.route("/shopify/webhook/cart-create", methods=["POST"])
def shopify_cart_create():
    """Handle Shopify abandoned cart/checkout webhook"""
    try:
        raw_data = request.get_data()
        if not _verify_shopify_hmac(raw_data, request.headers.get('X-Shopify-Hmac-Sha256', '')):
            return jsonify({'error': 'Unauthorized'}), 401

        data = request.json
        logger.info(f"🛒 Abandoned cart webhook received")
        logger.info(f"🔍 Webhook data: {json.dumps(data, indent=2)}")
        
        # Shopify sends different field structures for abandoned checkouts
        # Extract phone from multiple possible locations
        phone = None
        if data.get('phone'):
            phone = data.get('phone')
        elif data.get('customer') and data.get('customer', {}).get('phone'):
            phone = data.get('customer', {}).get('phone')
        elif data.get('billing_address') and data.get('billing_address', {}).get('phone'):
            phone = data.get('billing_address', {}).get('phone')
        elif data.get('customer') and data.get('customer', {}).get('default_address', {}).get('phone'):
            phone = data.get('customer', {}).get('default_address', {}).get('phone')
        
        logger.info(f"📞 Extracted phone: {phone}")
        
        # Use cart token as the unique ID — always present, unique per checkout.
        # data.get('id') is sometimes absent/null in Shopify webhook payloads,
        # which caused all carts to be stored as shopify_cart_id='None' and
        # each new cart replaced the previous one (INSERT OR REPLACE bug).
        cart_token = data.get('token') or data.get('cart_token') or str(data.get('id'))

        # Extract first name from multiple locations in the checkout payload
        customer = data.get('customer') or {}
        billing  = data.get('billing_address') or {}
        shipping = data.get('shipping_address') or {}
        first_name = (customer.get('first_name')
                      or billing.get('first_name')
                      or shipping.get('first_name')
                      or '')

        cart_data = {
            'id': cart_token,
            'customer_id': customer.get('id'),
            'first_name': first_name,
            'email': data.get('email'),
            'phone': phone,
            'token': cart_token,
            'line_items': data.get('line_items', []),
            'total_price': data.get('total_price') or data.get('subtotal_price'),
            'currency': data.get('currency', 'USD'),
            'abandoned_checkout_url': data.get('abandoned_checkout_url')
        }
        
        logger.info(f"📋 Cart data prepared: Phone={cart_data['phone']}, Email={cart_data['email']}, Items={len(cart_data['line_items'])}")
        
        # Store abandoned cart
        user_id = _get_webhook_user_id()
        if user_id:
            cart_id = db.add_abandoned_cart(user_id, cart_data)
            logger.info(f"✅ Abandoned cart stored: {cart_id} (user_id={user_id})")
            if not phone:
                logger.warning(f"⚠️  Cart {cart_id} has no phone number - won't be able to send reminder")
            else:
                # Enroll in any active flows for abandoned_cart trigger
                phone_e164 = _normalize_phone_webhook(phone)
                if phone_e164:
                    active_flows = db.get_active_flows_by_trigger(user_id, 'abandoned_cart')
                    if active_flows:
                        ctx = build_trigger_context('abandoned_cart', data)
                        for flow in active_flows:
                            first_step = get_flow_first_step_key(db, flow['id'])
                            if first_step:
                                flow_enroll_participant(db, flow['id'], phone_e164, ctx, first_step)
        else:
            logger.error("❌ No users found - cannot store cart")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logger.error(f"❌ Error processing cart webhook: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/shopify/webhook/cart-update", methods=["POST"])
def shopify_cart_update():
    """Handle Shopify checkouts/update webhook.
    Shopify fires checkouts/create before the customer enters contact info.
    This handler catches the update when they fill in phone/email, so we
    can send a reminder if they abandon later.
    """
    try:
        raw_data = request.get_data()
        if not _verify_shopify_hmac(raw_data, request.headers.get('X-Shopify-Hmac-Sha256', '')):
            return jsonify({'error': 'Unauthorized'}), 401

        data = request.json
        cart_token = data.get('token') or data.get('cart_token')
        if not cart_token:
            return jsonify({"status": "ok"}), 200

        # Extract phone from multiple locations
        phone = (data.get('phone')
                 or (data.get('customer') or {}).get('phone')
                 or (data.get('billing_address') or {}).get('phone')
                 or (data.get('shipping_address') or {}).get('phone'))
        email = data.get('email') or (data.get('customer') or {}).get('email')

        if not phone and not email:
            return jsonify({"status": "ok"}), 200  # Still no contact info, nothing to update

        user_id = _get_webhook_user_id()
        if not user_id:
            return jsonify({"status": "ok"}), 200

        # Update the existing cart record with phone/email now that we have it
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE abandoned_carts
                    SET customer_phone = COALESCE(NULLIF(?, ''), customer_phone),
                        customer_email = COALESCE(NULLIF(?, ''), customer_email)
                    WHERE shopify_cart_id = ? AND reminder_sent = 0 AND recovered = 0
                ''', (phone, email, cart_token))
                updated = cursor.rowcount
                conn.commit()
            if updated:
                logger.info(f"✅ Cart {cart_token} updated with phone={phone}, email={email}")
            else:
                logger.debug(f"Cart {cart_token} not found or already sent/recovered")
        except Exception as e:
            logger.warning(f"Could not update cart contact info: {e}")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logger.error(f"❌ Error processing cart update webhook: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/shopify/webhook/order-create", methods=["POST"])
def shopify_order_create():
    """Handle Shopify order creation webhook — stores order + auto-sends confirmation."""
    try:
        raw_data = request.get_data()
        if not _verify_shopify_hmac(raw_data, request.headers.get('X-Shopify-Hmac-Sha256', '')):
            return jsonify({'error': 'Unauthorized'}), 401

        data = request.json
        logger.info(f"📦 Order webhook received: Order #{data.get('order_number') or data.get('name')}")

        # Extract phone from multiple locations
        phone = (data.get('phone')
                 or (data.get('customer') or {}).get('phone')
                 or (data.get('billing_address') or {}).get('phone'))

        logger.info(f"📞 Extracted phone: {phone}")

        order_data = {
            'id': str(data.get('id')),
            'order_number': str(data.get('order_number') or data.get('name', '')),
            'customer': data.get('customer', {}),
            'email': data.get('email'),
            'phone': phone,
            'total_price': data.get('total_price'),
            'currency': data.get('currency', 'INR'),
            'financial_status': data.get('financial_status'),
            'fulfillment_status': data.get('fulfillment_status'),
            'line_items': data.get('line_items', [])
        }

        user_id = _get_webhook_user_id()
        if not user_id:
            logger.error("❌ No users found - cannot store order")
            return jsonify({"status": "ok"}), 200

        order_db_id = db.add_order(user_id, order_data)
        logger.info(f"✅ Order stored: DB id={order_db_id} (user_id={user_id})")

        # Store Shopify's customer-facing order page — used later by /track/<order_ref>
        try:
            db.save_order_status_url(str(data.get('id', '')), data.get('order_status_url'))
        except Exception as e:
            logger.warning(f"Could not save order status URL: {e}")

        # Mark any abandoned cart as recovered
        cart_token = data.get('cart_token')
        if cart_token:
            db.mark_cart_recovered(cart_token)
            logger.info(f"✅ Cart recovered: {cart_token}")

        # ---- Auto-send order confirmation if enabled ----
        if phone:
            settings = db.get_automation_settings(user_id)
            s = settings.get('order_confirmation', {})
            template_name = (s.get('template_name') or '').strip()

            if s.get('enabled') and template_name and not _has_active_flow(user_id, 'order_confirmation'):
                phone_e164 = _normalize_phone_webhook(phone)
                if phone_e164:
                    first_name = (data.get('customer') or {}).get('first_name') or 'there'
                    line_items = data.get('line_items', [])
                    order_number = order_data['order_number']
                    # Format: #F1<number> — e.g. #F14123
                    order_number_display = f"#F1{order_number}"
                    items_str = _format_items(line_items)
                    total = f"₹{order_data['total_price']}" if order_data['total_price'] else ''
                    # Template params: {{1}}=name, {{2}}=order#, {{3}}=items, {{4}}=total
                    params = [str(first_name), order_number_display, items_str, total]
                    lang = s.get('template_language') or 'en_US'

                    # Upload first product image for IMAGE header (non-fatal if fails)
                    image_url = _get_product_image_url(line_items)
                    header_media_id = _upload_image_from_url(image_url) if image_url else None

                    success, _ = _send_automation_message(
                        phone_e164, 'order_confirmation', template_name, lang, params,
                        header_media_id=header_media_id
                    )
                    if success:
                        db.mark_order_confirmation_sent(order_db_id)
                    db.log_activity(
                        user_id=user_id,
                        username='System',
                        action=('Automation: Order Confirmation Sent'
                                if success else 'Automation: Order Confirmation Failed'),
                        details=f"Order {order_number_display} → {phone_e164}"
                    )
            elif s.get('enabled') and template_name:
                logger.info(f"Skipping legacy order_confirmation automation for user {user_id} — active flow owns this trigger")

            # Enroll in any active flows for order_confirmation trigger
            phone_e164 = _normalize_phone_webhook(phone) if phone else None
            if phone_e164:
                active_flows = db.get_active_flows_by_trigger(user_id, 'order_confirmation')
                if active_flows:
                    ctx = build_trigger_context('order_confirmation', data)
                    for flow in active_flows:
                        first_step = get_flow_first_step_key(db, flow['id'])
                        if first_step:
                            flow_enroll_participant(db, flow['id'], phone_e164, ctx, first_step)
        else:
            logger.warning(f"⚠️ Order {order_db_id} has no phone — skipping confirmation")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logger.error(f"❌ Error processing order webhook: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/shopify/webhook/fulfillment", methods=["POST"])
def shopify_fulfillment():
    """Handle Shopify fulfillment webhook (orders/fulfilled OR fulfillments/create topic).
    Sends a dispatch notification to the customer."""
    try:
        raw_data = request.get_data()
        if not _verify_shopify_hmac(raw_data, request.headers.get('X-Shopify-Hmac-Sha256', '')):
            return jsonify({'error': 'Unauthorized'}), 401

        data = request.json
        topic = request.headers.get('X-Shopify-Topic', '')
        logger.info(f"🚚 Fulfillment webhook received (topic: {topic})")

        # Determine if payload is a full order (orders/fulfilled) or a fulfillment object
        is_fulfillment_object = ('order_id' in data and 'order_number' not in data
                                 and 'fulfillments' not in data)

        user_id = _get_webhook_user_id()
        if not user_id:
            return jsonify({"status": "ok"}), 200

        if is_fulfillment_object:
            # fulfillments/create payload — look up order from DB
            shopify_order_id = str(data.get('order_id', ''))
            tracking_number = data.get('tracking_number') or 'Will be provided'
            tracking_url    = data.get('tracking_url') or ''
            courier_name    = data.get('tracking_company') or 'our courier'
            # fulfillments/create payloads carry no order_status_url; if the order was
            # seen by orders/create we already have it stored, so leave it untouched.
            status_url      = ''
            line_items = data.get('line_items', [])
            order = db.get_order_by_shopify_id(shopify_order_id)
            if not order:
                logger.warning(f"⚠️ Order {shopify_order_id} not in DB — cannot send fulfillment msg")
                return jsonify({"status": "ok", "note": "order not found"}), 200
            # Fallback: fulfillments/create payloads carry no courier tracking_url
            # and no order_status_url of their own — fall back to the order's
            # already-stored order_status_url (set from orders/create), same
            # fallback the orders/fulfilled branch below already applies.
            if not tracking_url:
                tracking_url = order.get('order_status_url') or ''
            phone = order.get('customer_phone')
            order_number = order.get('order_number', '')
            first_name = 'there'
            order_db_id = order['id']
            # If line_items not in fulfillment payload, restore from stored order
            if not line_items:
                try:
                    line_items = json.loads(order.get('order_items') or '[]')
                except Exception:
                    line_items = []
            db.mark_order_fulfillment_received(shopify_order_id)
        else:
            # orders/fulfilled payload — full order object
            shopify_order_id = str(data.get('id', ''))
            order_number = str(data.get('order_number') or data.get('name', ''))
            phone = (data.get('phone')
                     or (data.get('customer') or {}).get('phone')
                     or (data.get('billing_address') or {}).get('phone'))
            first_name = (data.get('customer') or {}).get('first_name') or 'there'
            line_items = data.get('line_items', [])

            # Get tracking info from last fulfillment
            fulfillments = data.get('fulfillments') or []
            tracking_number = 'Will be provided'
            tracking_url    = ''
            courier_name    = 'our courier'
            if fulfillments:
                last = fulfillments[-1]
                tracking_number = last.get('tracking_number') or 'Will be provided'
                tracking_url    = last.get('tracking_url') or ''
                courier_name    = last.get('tracking_company') or 'our courier'

            # Shopify's customer-facing order page — the primary /track/ destination
            status_url = data.get('order_status_url') or ''

            # Fallback: use Shopify's order status page if no courier URL
            if not tracking_url:
                tracking_url = status_url

            # Upsert order so we have an id
            order_data_payload = {
                'id': shopify_order_id,
                'order_number': order_number,
                'customer': data.get('customer', {}),
                'email': data.get('email'),
                'phone': phone,
                'total_price': data.get('total_price'),
                'currency': data.get('currency', 'INR'),
                'financial_status': data.get('financial_status'),
                'fulfillment_status': 'fulfilled',
                'line_items': line_items
            }
            order_db_id = db.add_order(user_id, order_data_payload)
            db.mark_order_fulfillment_received(shopify_order_id)

        # Save tracking URL for /track/<order_ref> redirect
        # tracking_url is courier URL if available, otherwise Shopify order status page
        if tracking_url:
            try:
                awb = tracking_number if tracking_number != 'Will be provided' else None
                db.save_order_tracking_url(
                    shopify_order_id, tracking_url,
                    tracking_number=awb,
                    tracking_company=(courier_name if courier_name != 'our courier' else None),
                    order_status_url=(status_url or None)
                )
                logger.info(f"📌 Tracking saved for order {shopify_order_id}: "
                            f"{tracking_url} (awb={awb}, courier={courier_name}, "
                            f"status_url={'yes' if status_url else 'no'})")
            except Exception as e:
                logger.warning(f"Could not save tracking URL: {e}")

        order_number_display = f"#F1{order_number}"
        logger.info(f"📞 Fulfillment phone: {phone}, order: {order_number_display}, "
                    f"tracking: {tracking_number}")

        # ---- Auto-send dispatch notification if enabled ----
        if phone:
            settings = db.get_automation_settings(user_id)
            s = settings.get('fulfillment', {})
            template_name = (s.get('template_name') or '').strip()

            if s.get('enabled') and template_name and not _has_active_flow(user_id, 'fulfillment'):
                phone_e164 = _normalize_phone_webhook(phone)
                if phone_e164:
                    lang = s.get('template_language') or 'en_US'
                    items_str = _format_items(line_items)
                    # Every value the template *could* ask for, in variable order:
                    #   {{1}}=name  {{2}}=order#  {{3}}=courier  {{4}}=items
                    #   {{5}}=tracking#  {{6}}=courier tracking link (body-link variant)
                    # The approved template decides how many are actually sent.
                    link_for_body = tracking_url or 'https://boxbox.in'
                    all_params = [str(first_name), order_number_display, courier_name,
                                  items_str, tracking_number, link_for_body]

                    shape = _template_shape(template_name, lang)
                    if shape:
                        params = all_params[:shape['body_vars']]
                        # Dynamic URL button → suffix is the order number, resolved by /track/.
                        # No such button on the template → send none, or Meta returns 132018.
                        btn_params = ({"url_index_0": str(order_number)}
                                      if shape['has_dynamic_url_button'] else None)
                        logger.info(f"fulfillment template '{template_name}': "
                                    f"{shape['body_vars']} body vars, "
                                    f"url button={'yes' if btn_params else 'no'}")
                    else:
                        # Couldn't inspect the template — keep the last known-good shape.
                        params = all_params[:5]
                        btn_params = {"url_index_0": str(order_number)}

                    success, _ = _send_automation_message(
                        phone_e164, 'fulfillment', template_name, lang, params,
                        button_params=btn_params
                    )
                    if success:
                        db.mark_fulfillment_sent(order_db_id)
                    db.log_activity(
                        user_id=user_id,
                        username='System',
                        action=('Automation: Dispatch Notification Sent'
                                if success else 'Automation: Dispatch Notification Failed'),
                        details=f"Order {order_number_display} → {phone_e164}, tracking={tracking_number}"
                    )
            elif s.get('enabled') and template_name:
                logger.info(f"Skipping legacy fulfillment automation for user {user_id} — active flow owns this trigger")

            # Enroll in any active flows for fulfillment trigger
            phone_e164 = _normalize_phone_webhook(phone) if phone else None
            if phone_e164:
                active_flows = db.get_active_flows_by_trigger(user_id, 'fulfillment')
                if active_flows:
                    # build_trigger_context reads customer/order_number/line_items/
                    # fulfillments straight off the raw payload, but this webhook
                    # accepts two different Shopify shapes (full order vs. bare
                    # fulfillment object) and the block above already resolved the
                    # correct first_name/order_number/line_items/tracking_url for
                    # either shape — feed those in so flows get the same values
                    # the dispatch notification above used, not a re-derivation
                    # that's wrong for the fulfillments/create shape (no top-level
                    # customer/order_number, and tracking_url may come from the
                    # order_status_url fallback rather than data['fulfillments']).
                    ctx_data = dict(data)
                    ctx_data['customer'] = {'first_name': first_name}
                    ctx_data['order_number'] = order_number
                    ctx_data['line_items'] = line_items
                    ctx_data['fulfillments'] = [{'tracking_url': tracking_url}]
                    ctx_data['courier_name'] = courier_name
                    ctx_data['tracking_number'] = tracking_number
                    ctx = build_trigger_context('fulfillment', ctx_data)
                    for flow in active_flows:
                        first_step = get_flow_first_step_key(db, flow['id'])
                        if first_step:
                            flow_enroll_participant(db, flow['id'], phone_e164, ctx, first_step)
        else:
            logger.warning("⚠️ Fulfillment webhook has no phone — skipping notification")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logger.error(f"❌ Error processing fulfillment webhook: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/shopify/webhook/order-cancelled", methods=["POST"])
def shopify_order_cancelled():
    """Handle Shopify order cancellation webhook (orders/cancelled topic).
    Can also handle refunds/create, which indicates order was refunded/cancelled."""
    try:
        raw_data = request.get_data()
        if not _verify_shopify_hmac(raw_data, request.headers.get('X-Shopify-Hmac-Sha256', '')):
            return jsonify({'error': 'Unauthorized'}), 401

        data = request.json
        topic = request.headers.get('X-Shopify-Topic', '')
        logger.info(f"❌ Order cancelled webhook received (topic: {topic})")

        phone = (data.get('phone')
                 or (data.get('customer') or {}).get('phone')
                 or (data.get('billing_address') or {}).get('phone'))

        user_id = _get_webhook_user_id()
        if not user_id:
            return jsonify({"status": "ok"}), 200

        if phone:
            phone_e164 = _normalize_phone_webhook(phone)
            if phone_e164:
                # Enroll in any active flows for order_cancelled trigger
                active_flows = db.get_active_flows_by_trigger(user_id, 'order_cancelled')
                if active_flows:
                    ctx = build_trigger_context('order_cancelled', data)
                    for flow in active_flows:
                        first_step = get_flow_first_step_key(db, flow['id'])
                        if first_step:
                            flow_enroll_participant(db, flow['id'], phone_e164, ctx, first_step)
                    logger.info(f"Enrolled {phone_e164} in {len(active_flows)} order_cancelled flow(s)")
        else:
            logger.warning("⚠️ Order cancellation webhook has no phone — skipping flow enrollment")

        return jsonify({"status": "ok"}), 200


@app.route("/shopify/webhook/order-refunded", methods=["POST"])
def shopify_order_refunded():
    """Handle Shopify refunds/create webhook (refund event).
    Refunds webhook payload only contains refund object with order_id reference.
    Must look up full order in DB to get customer phone/name for flow enrollment."""
    try:
        raw_data = request.get_data()
        if not _verify_shopify_hmac(raw_data, request.headers.get('X-Shopify-Hmac-Sha256', '')):
            return jsonify({'error': 'Unauthorized'}), 401

        data = request.json
        topic = request.headers.get('X-Shopify-Topic', '')
        logger.info(f"💰 Refund webhook received (topic: {topic})")

        user_id = _get_webhook_user_id()
        if not user_id:
            return jsonify({"status": "ok"}), 200

        # Refunds/create payload has order_id reference, not full order object
        order_id = data.get('order_id')
        if not order_id:
            logger.warning("⚠️ Refund webhook missing order_id — skipping enrollment")
            return jsonify({"status": "ok"}), 200

        # Look up the order in shopify_orders table
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM shopify_orders WHERE shopify_order_id = ?',
                (str(order_id),)
            )
            order_record = cursor.fetchone()

        if not order_record:
            logger.warning(f"⚠️ Refund webhook references unknown order {order_id} — skipping enrollment")
            return jsonify({"status": "ok"}), 200

        order_record = dict(order_record)
        phone = order_record.get('customer_phone')

        if phone:
            phone_e164 = _normalize_phone_webhook(phone)
            if phone_e164:
                # Enroll in any active flows for order_refunded trigger
                active_flows = db.get_active_flows_by_trigger(user_id, 'order_refunded')
                if active_flows:
                    # Build context from the stored order record, enhanced with refund data
                    ctx_data = {
                        'customer': {
                            'first_name': order_record.get('customer_email', '').split('@')[0] if order_record.get('customer_email') else '',
                            'email': order_record.get('customer_email', ''),
                            'phone': phone
                        },
                        'order_number': order_record.get('order_number', ''),
                        'total_price': order_record.get('total_price', ''),
                        'line_items': [],
                        'refund': data
                    }
                    # Try to parse stored order_items
                    try:
                        if order_record.get('order_items'):
                            ctx_data['line_items'] = json.loads(order_record['order_items'])
                    except Exception:
                        pass

                    ctx = build_trigger_context('order_refunded', ctx_data)
                    for flow in active_flows:
                        first_step = get_flow_first_step_key(db, flow['id'])
                        if first_step:
                            flow_enroll_participant(db, flow['id'], phone_e164, ctx, first_step)
                    logger.info(f"Enrolled {phone_e164} in {len(active_flows)} order_refunded flow(s)")
        else:
            logger.warning("⚠️ Refund webhook order has no phone — skipping flow enrollment")

        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Error handling refund webhook: {e}", exc_info=True)
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logger.error(f"❌ Error processing order cancellation webhook: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/shopify/webhook/customer-created", methods=["POST"])
def shopify_customer_created():
    """Handle Shopify customer creation webhook (customers/create topic).
    Enrolls customer in welcome/new customer flows."""
    try:
        raw_data = request.get_data()
        if not _verify_shopify_hmac(raw_data, request.headers.get('X-Shopify-Hmac-Sha256', '')):
            return jsonify({'error': 'Unauthorized'}), 401

        data = request.json
        topic = request.headers.get('X-Shopify-Topic', '')
        logger.info(f"👤 Customer created webhook received (topic: {topic})")

        phone = data.get('phone')
        email = data.get('email')

        user_id = _get_webhook_user_id()
        if not user_id:
            return jsonify({"status": "ok"}), 200

        if phone:
            phone_e164 = _normalize_phone_webhook(phone)
            if phone_e164:
                # Enroll in any active flows for customer_created trigger
                active_flows = db.get_active_flows_by_trigger(user_id, 'customer_created')
                if active_flows:
                    ctx = build_trigger_context('customer_created', data)
                    for flow in active_flows:
                        first_step = get_flow_first_step_key(db, flow['id'])
                        if first_step:
                            flow_enroll_participant(db, flow['id'], phone_e164, ctx, first_step)
                    logger.info(f"Enrolled {phone_e164} in {len(active_flows)} customer_created flow(s)")
        else:
            logger.warning(f"⚠️ New customer {email} has no phone — skipping flow enrollment")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logger.error(f"❌ Error processing customer creation webhook: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# ============================================================
# AUTOMATED MESSAGE SENDING
# ============================================================

@app.route("/api/send-cart-reminders", methods=["POST"])
@login_required
def send_cart_reminders():
    """Send reminders for abandoned carts"""
    try:
        unsent_carts = db.get_unsent_cart_reminders(current_user.id)
        
        sent_count = 0
        failed_count = 0
        
        for cart in unsent_carts:
            phone = cart['customer_phone']
            cart_items = json.loads(cart['cart_items']) if cart['cart_items'] else []
            
            # Build product list
            products = []
            for item in cart_items[:3]:  # Show first 3 items
                products.append(f"• {item.get('title', 'Product')}")
            
            product_list = "\n".join(products)
            if len(cart_items) > 3:
                product_list += f"\n...and {len(cart_items) - 3} more items"
            
            message = f"""Hi! 👋

You left some items in your cart:

{product_list}

Total: {cart.get('currency', '$')}{cart.get('total_price', '0')}

Complete your purchase now! 🛒✨"""
            
            # Send message
            status_code, response = send_text(phone, message)
            
            if status_code == 200:
                db.mark_cart_reminder_sent(cart['id'])
                sent_count += 1
                logger.info(f"✅ Cart reminder sent to {phone}")
            else:
                failed_count += 1
                logger.error(f"❌ Failed to send cart reminder to {phone}")
        
        db.log_activity(
            user_id=current_user.id,
            username=current_user.username,
            action='Send Cart Reminders',
            details=f'Sent {sent_count} cart reminders, {failed_count} failed',
            ip_address=request.remote_addr
        )
        
        return jsonify({
            'success': True,
            'sent': sent_count,
            'failed': failed_count,
            'message': f'Sent {sent_count} cart reminders'
        })
        
    except Exception as e:
        logger.error(f"❌ Error sending cart reminders: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})


@app.route("/api/send-order-confirmations", methods=["POST"])
@login_required
def send_order_confirmations():
    """Send confirmations for new orders"""
    try:
        unsent_orders = db.get_unsent_order_confirmations(current_user.id)
        
        sent_count = 0
        failed_count = 0
        
        for order in unsent_orders:
            phone = order['customer_phone']
            order_items = json.loads(order['order_items']) if order['order_items'] else []
            
            # Build product list
            products = []
            for item in order_items[:3]:
                products.append(f"• {item.get('title', 'Product')} x{item.get('quantity', 1)}")
            
            product_list = "\n".join(products)
            if len(order_items) > 3:
                product_list += f"\n...and {len(order_items) - 3} more items"
            
            message = f"""✅ Order Confirmed! 

Order #{order['order_number']}

{product_list}

Total: {order.get('currency', '$')}{order.get('total_price', '0')}

Thank you for your purchase! 🎉
We'll send you updates on your order."""
            
            # Send message
            status_code, response = send_text(phone, message)
            
            if status_code == 200:
                db.mark_order_confirmation_sent(order['id'])
                sent_count += 1
                logger.info(f"✅ Order confirmation sent to {phone}")
            else:
                failed_count += 1
                logger.error(f"❌ Failed to send order confirmation to {phone}")
        
        db.log_activity(
            user_id=current_user.id,
            username=current_user.username,
            action='Send Order Confirmations',
            details=f'Sent {sent_count} order confirmations, {failed_count} failed',
            ip_address=request.remote_addr
        )
        
        return jsonify({
            'success': True,
            'sent': sent_count,
            'failed': failed_count,
            'message': f'Sent {sent_count} order confirmations'
        })
        
    except Exception as e:
        logger.error(f"❌ Error sending order confirmations: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})


# ============================================================
# QUICK MESSAGE API
# ============================================================

@app.route('/api/send-quick-message', methods=['POST'])
@login_required
def send_quick_message():
    """Send a quick message to a specific phone number"""
    try:
        data = request.json
        phone = data.get('phone')
        message = data.get('message')
        
        if not phone or not message:
            return jsonify({'success': False, 'error': 'Phone and message are required'}), 400
        
        # Send message (returns tuple: success, error_message)
        success, error_message = send_text(phone, message)
        
        if success:
            # Log the activity
            db.log_activity(
                user_id=current_user.id,
                username=current_user.username,
                action='Quick Reply Sent',
                details=f'Sent message to {phone}',
                ip_address=request.remote_addr
            )
            
            return jsonify({'success': True, 'message': 'Message sent successfully'})
        else:
            return jsonify({'success': False, 'error': error_message or 'Failed to send message'}), 500
            
    except Exception as e:
        logger.error(f"Error sending quick message: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================
# GRACEFUL SHUTDOWN
# ============================================================

def cleanup():
    """Shutdown message queue gracefully"""
    logger.info("🛑 Shutting down message queue...")
    message_queue.stop()
    logger.info("✅ Cleanup complete")

# Register cleanup for normal exit
atexit.register(cleanup)

# Register cleanup for Ctrl+C (only in main thread)
def signal_handler(sig, frame):
    cleanup()
    sys.exit(0)

# Only register signal handler if we're in the main thread
if threading.current_thread() is threading.main_thread():
    signal.signal(signal.SIGINT, signal_handler)


# ============================================================
# RUN APP
# ============================================================

if __name__ == "__main__":
    try:
        # Get configuration from environment
        DEBUG_MODE = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
        HOST = os.getenv('FLASK_HOST', '127.0.0.1')
        PORT = int(os.getenv('FLASK_PORT', '5000'))
        
        logger.info("\n" + "="*50)
        logger.info("🚀 Starting WhatsApp Bulk Sender")
        logger.info(f"🌐 Host: {HOST}:{PORT}")
        logger.info(f"🐛 Debug Mode: {DEBUG_MODE}")
        logger.info(f"📊 Queue monitoring: http://{HOST}:{PORT}/queue-status")
        logger.info(f"📈 Queue stats API: http://{HOST}:{PORT}/queue-stats")
        logger.info("="*50 + "\n")
        
        app.run(debug=DEBUG_MODE, host=HOST, port=PORT)
    except KeyboardInterrupt:
        logger.info("🛑 Keyboard interrupt received")
        cleanup()
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        cleanup()
        raise