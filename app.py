from flask import Flask, render_template, request, flash, redirect, jsonify, url_for, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import pandas as pd
import os
import sys
import signal
import atexit
import threading
import logging
from datetime import datetime

from utils.personalize import personalize
from utils.whatsapp import send_text, get_templates, send_template, upload_media
from utils.logger import log_message
from utils.rate_limiter import RateLimiter, MessageQueue
from utils.background_scheduler import schedule_message_job, get_scheduled_jobs, cancel_job
from utils.auth import UserManager
from utils.database import Database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
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


@app.route("/signup", methods=["GET", "POST"])
def signup():
    """Signup page"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == "POST":
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validation
        if not username or not email or not password:
            flash("All fields are required", "error")
            return redirect(url_for('signup'))
        
        if len(username) < 3 or len(username) > 20:
            flash("Username must be 3-20 characters", "error")
            return redirect(url_for('signup'))
        
        if not username.isalnum():
            flash("Username can only contain letters and numbers", "error")
            return redirect(url_for('signup'))
        
        if password != confirm_password:
            flash("Passwords do not match", "error")
            return redirect(url_for('signup'))
        
        if len(password) < 8:
            flash("Password must be at least 8 characters", "error")
            return redirect(url_for('signup'))
        
        # Create user
        user, error = user_manager.create_user(username, email, password)
        
        if error:
            flash(error, "error")
            return redirect(url_for('signup'))
        
        logger.info(f"New user registered: {username}")
        
        # Log activity
        db.log_activity(
            user_id=user.id,
            username=username,
            action='Registration',
            details='New user account created',
            ip_address=request.remote_addr
        )
        
        flash("Account created successfully! Please login.", "success")
        return redirect(url_for('login'))
    
    return render_template('signup.html')


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
        
        # Get header image file if provided
        header_image_file = request.files.get('header_image')
        
        if header_image_file and header_image_file.filename:
            logger.info(f"📎 Received image file: {header_image_file.filename}")
            # Get file size
            header_image_file.seek(0, 2)
            file_size = header_image_file.tell()
            header_image_file.seek(0)
            logger.info(f"📎 File size: {file_size} bytes")
        
        from utils.whatsapp import create_template
        
        status, response = create_template(WABA_ID, template_data, header_image_file)
        
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
        df = pd.read_csv(csv_file)
        columns = list(df.columns)
        return jsonify({"columns": columns})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/template-info")
@login_required
def template_info():
    """Get template parameter count"""
    template_name = request.args.get("name")
    templates = get_templates(WABA_ID)

    selected = next((t for t in templates if t["name"] == template_name), None)

    count = 0
    if selected:
        body = next((c for c in selected["components"] if c["type"] == "BODY"), None)
        if body and "text" in body:
            count = body["text"].count("{{")

    return jsonify({"count": count})


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
        csv_file = request.files.get("csv_file")
        template_name = request.form.get("template_name")
        message_template = request.form.get("message_template")
        send_mode = request.form.get("send_mode")
        send_time = request.form.get("send_time")

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
            df = pd.read_csv(csv_file, encoding='utf-8')
        except UnicodeDecodeError:
            logger.warning("UTF-8 decode failed, trying latin-1 encoding")
            csv_file.seek(0)
            try:
                df = pd.read_csv(csv_file, encoding='latin-1')
            except Exception as e:
                flash(f"❌ Error reading CSV: {str(e)}", "error")
                return redirect("/")
        except Exception as e:
            flash(f"❌ Error reading CSV: {str(e)}", "error")
            return redirect("/")

        # Check if DataFrame is empty
        if len(df) == 0:
            flash("❌ CSV file is empty. Please add contacts to the file.", "error")
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

        if selected_template:
            template_language = selected_template.get("language", "en")
            body_component = next(
                (c for c in selected_template["components"] if c["type"] == "BODY"),
                None
            )
            if body_component and "text" in body_component:
                template_param_count = body_component["text"].count("{{")
        
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
                
                success, message = schedule_message_job(
                    df=df,
                    template_name=template_name,
                    template_language=template_language,
                    template_params_mapping=params_mapping,
                    send_time_str=schedule_datetime_str,
                    header_media_id=header_media_id,
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
        
        # Create campaign record
        campaign_name = f"Campaign {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        campaign_type = 'Template' if selected_template else 'Text'
        campaign_id = db.create_campaign(
            user_id=current_user.id,
            username=current_user.username,
            campaign_name=campaign_name,
            campaign_type=campaign_type,
            template_name=template_name if selected_template else None,
            recipient_count=len(df),
            scheduled_time=None
        )
        
        # Set campaign status to running
        db.update_campaign_status(campaign_id, 'running')
        
        # Log campaign creation
        db.log_activity(
            user_id=current_user.id,
            username=current_user.username,
            action='Campaign Started',
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

                # Add message record to database
                message_id = db.add_message(
                    campaign_id=campaign_id,
                    user_id=current_user.id,
                    phone_number=phone,
                    recipient_name=name,
                    template_name=template_name,
                    status='queued'
                )

                # Add to queue instead of sending immediately
                message_queue.add_message(
                    send_template,
                    phone,
                    template_name,
                    params,
                    template_language,
                    header_media_id=header_media_id,
                    user_id=current_user.id,
                    username=current_user.username,
                    campaign_id=campaign_id,
                    message_id=message_id  # Pass message_id to rate limiter
                )

            flash(f"✅ {len(df)} template messages queued for sending! Monitor progress at /queue-status", "success")
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
                    message_id=message_id  # Pass message_id to rate limiter
                )

            flash(f"✅ {len(df)} text messages queued for sending! Monitor progress at /queue-status", "success")
            return redirect("/")

    return render_template(
        "index.html",
        results=results,
        templates=templates,
        template_param_count=template_param_count,
        csv_columns=csv_columns,
        current_date=datetime.now().strftime('%Y-%m-%d')
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
    campaigns = db.get_user_campaigns(current_user.id, limit=50)
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


@app.route("/activity-log")
@login_required
def activity_log_page():
    """View activity log"""
    activities = db.get_user_activity(current_user.id, limit=100)
    return render_template('activity_log.html', activities=activities)


@app.route("/api/dashboard-stats")
@login_required
def api_dashboard_stats():
    """API endpoint for dashboard statistics"""
    stats = db.get_dashboard_stats(user_id=current_user.id)
    return jsonify(stats)


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
        
        logger.info(f"📊 Status update: {message_id} -> {status}")
        
        if status == "delivered":
            logger.info(f"🚀 Processing delivered status for message: {message_id}")
            db.update_message_engagement(message_id, "delivered", timestamp)
            logger.info(f"✅ Delivered status processed")
        elif status == "read":
            logger.info(f"👁️ Processing read status for message: {message_id}")
            db.update_message_engagement(message_id, "read", timestamp)
            logger.info(f"✅ Read status processed")
        elif status == "failed":
            error = status_data.get("errors", [{}])[0]
            error_message = error.get("message", "Unknown error")
            logger.error(f"❌ Message {message_id} failed: {error_message}")
    
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
        
        # Check if this is a reply to our message (has context)
        context = message_data.get("context")
        if context and context.get("id"):
            original_message_id = context["id"]
            logger.info(f"💬 Reply with context to message: {original_message_id}")
            db.update_message_engagement(original_message_id, "replied", timestamp)
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
                        db.update_message_engagement(msg_id, "replied", timestamp)
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