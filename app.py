from flask import Flask, render_template, request, flash, redirect, jsonify, url_for, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import pandas as pd
import os
import sys
import signal
import atexit
import threading
import logging
import json
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
    """Get template parameter count and button information"""
    template_name = request.args.get("name")
    templates = get_templates(WABA_ID)

    selected = next((t for t in templates if t["name"] == template_name), None)

    count = 0
    buttons = []
    
    if selected:
        body = next((c for c in selected["components"] if c["type"] == "BODY"), None)
        if body and "text" in body:
            count = body["text"].count("{{")
        
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

    return jsonify({"count": count, "buttons": buttons})


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
                    button_params=button_params if button_params else None,
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
        customers = shopify.fetch_customers()
        
        logger.info(f"📊 Fetched {len(customers)} customers from Shopify")
        
        # Debug: Log first customer's raw data if available
        if customers:
            first = customers[0]
            logger.info(f"🔍 First customer raw data - ID: {first.get('id')}, Name: {first.get('first_name')} {first.get('last_name')}, Phone: {first.get('phone')}, Address Phone: {first.get('default_address', {}).get('phone')}")
        
        synced_count = 0
        skipped_count = 0
        
        for customer in customers:
            customer_data = shopify.parse_customer_data(customer)
            logger.info(f"🔍 Parsed customer: {customer_data['first_name']} {customer_data['last_name']} - Phone: '{customer_data['phone']}'")
            
            if customer_data['phone']:  # Only add customers with phone numbers
                db.add_or_update_customer(current_user.id, customer_data)
                synced_count += 1
                logger.info(f"✅ Synced customer: {customer_data['first_name']} {customer_data['last_name']} - {customer_data['phone']}")
            else:
                skipped_count += 1
                logger.warning(f"⚠️ Skipped customer (no phone): {customer_data.get('first_name')} {customer_data.get('last_name')} - Email: {customer_data.get('email')}")
        
        logger.info(f"📊 Sync complete - Synced: {synced_count}, Skipped (no phone): {skipped_count}")
        
        db.log_activity(
            user_id=current_user.id,
            username=current_user.username,
            action='Shopify Sync',
            details=f'Synced {synced_count} customers from Shopify (Skipped {skipped_count} without phone numbers)',
            ip_address=request.remote_addr
        )
        
        message = f'Successfully synced {synced_count} customers from Shopify'
        if skipped_count > 0:
            message += f' ({skipped_count} customers skipped - no phone number)'
        
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
        recipient_id = status_data.get("recipient_id")
        
        logger.info(f"📊 Status update: {message_id} -> {status}")
        
        if status == "delivered":
            logger.info(f"🚀 Processing delivered status for message: {message_id}")
            db.update_message_engagement(message_id, "delivered", timestamp)
            if recipient_id:
                db.update_customer_message_stats(recipient_id, "sent")
            logger.info(f"✅ Delivered status processed")
        elif status == "read":
            logger.info(f"👁️ Processing read status for message: {message_id}")
            db.update_message_engagement(message_id, "read", timestamp)
            if recipient_id:
                db.update_customer_message_stats(recipient_id, "read")
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
        
        # Check if this is a reply to our message (has context)
        context = message_data.get("context")
        if context and context.get("id"):
            original_message_id = context["id"]
            logger.info(f"💬 Reply with context to message: {original_message_id}")
            db.update_message_engagement(original_message_id, "replied", timestamp, reply_text)
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
        
        cart_data = {
            'id': str(data.get('id')),
            'customer_id': data.get('customer', {}).get('id') if data.get('customer') else None,
            'email': data.get('email'),
            'phone': phone,
            'token': data.get('token') or data.get('cart_token'),
            'line_items': data.get('line_items', []),
            'total_price': data.get('total_price') or data.get('subtotal_price'),
            'currency': data.get('currency', 'USD'),
            'abandoned_checkout_url': data.get('abandoned_checkout_url')
        }
        
        logger.info(f"📋 Cart data prepared: Phone={cart_data['phone']}, Email={cart_data['email']}, Items={len(cart_data['line_items'])}")
        
        # Store abandoned cart for all users
        users = user_manager.get_all_users()
        if users:
            user_id = users[0].id
            cart_id = db.add_abandoned_cart(user_id, cart_data)
            logger.info(f"✅ Abandoned cart stored: {cart_id}")
            
            if not phone:
                logger.warning(f"⚠️  Cart {cart_id} has no phone number - won't be able to send reminder")
        else:
            logger.error("❌ No users found - cannot store cart")
        
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        logger.error(f"❌ Error processing cart webhook: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/shopify/webhook/order-create", methods=["POST"])
def shopify_order_create():
    """Handle Shopify order creation webhook"""
    try:
        data = request.json
        logger.info(f"📦 Order webhook received: Order #{data.get('order_number') or data.get('name')}")
        logger.info(f"🔍 Order data: {json.dumps(data, indent=2)}")
        
        # Extract phone from multiple locations
        phone = None
        if data.get('phone'):
            phone = data.get('phone')
        elif data.get('customer') and data.get('customer', {}).get('phone'):
            phone = data.get('customer', {}).get('phone')
        elif data.get('billing_address') and data.get('billing_address', {}).get('phone'):
            phone = data.get('billing_address', {}).get('phone')
        
        logger.info(f"📞 Extracted phone: {phone}")
        
        order_data = {
            'id': str(data.get('id')),
            'order_number': str(data.get('order_number') or data.get('name', '')),
            'customer': data.get('customer', {}),
            'email': data.get('email'),
            'phone': phone,
            'total_price': data.get('total_price'),
            'currency': data.get('currency', 'USD'),
            'financial_status': data.get('financial_status'),
            'fulfillment_status': data.get('fulfillment_status'),
            'line_items': data.get('line_items', [])
        }
        
        logger.info(f"📋 Order data prepared: Order #{order_data['order_number']}, Phone={order_data['phone']}, Items={len(order_data['line_items'])}")
        
        # Store order for all users
        users = user_manager.get_all_users()
        if users:
            user_id = users[0].id
            order_id = db.add_order(user_id, order_data)
            logger.info(f"✅ Order stored: {order_id}")
            
            # Mark any abandoned cart as recovered
            cart_token = data.get('cart_token')
            if cart_token:
                db.mark_cart_recovered(cart_token)
                logger.info(f"✅ Cart recovered: {cart_token}")
            
            if not phone:
                logger.warning(f"⚠️  Order {order_id} has no phone number - won't be able to send confirmation")
        else:
            logger.error("❌ No users found - cannot store order")
        
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        logger.error(f"❌ Error processing order webhook: {e}", exc_info=True)
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