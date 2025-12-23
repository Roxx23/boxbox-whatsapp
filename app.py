from flask import Flask, render_template, request, flash, redirect, jsonify
import pandas as pd
import os
import sys
import signal
import atexit
import threading

from utils.personalize import personalize
from utils.whatsapp import send_text, get_templates, send_template, upload_media
from utils.logger import log_message
from utils.rate_limiter import RateLimiter, MessageQueue
from utils.background_scheduler import schedule_message_job, get_scheduled_jobs, cancel_job

# Load from environment variables
WABA_ID = os.getenv('WABA_ID', "2252354741929132")

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'change-this-in-production')

# Initialize GLOBAL rate limiter and message queue
# These persist across requests
rate_limiter = RateLimiter(max_requests=20, time_window=1.0)
message_queue = MessageQueue(rate_limiter, num_workers=1)
message_queue.start()  # Start worker threads

print("✅ Message queue started successfully")

# Connect message queue to scheduler
from utils.background_scheduler import set_message_queue
set_message_queue(message_queue)


# ============================================================
# TEMPLATE ROUTES
# ============================================================

@app.route("/create-template", methods=["GET"])
def create_template_page():
    """Render template creation page"""
    return render_template("create_template.html")


@app.route("/submit-template", methods=["POST"])
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
        
        from utils.whatsapp import create_template
        
        status, response = create_template(WABA_ID, template_data, None)
        
        if status in [200, 201]:
            flash(f"✅ Template '{template_data['template_name']}' submitted successfully! It will be reviewed by WhatsApp.", "success")
        else:
            error_msg = "Unknown error"
            if 'error' in response:
                if isinstance(response['error'], dict):
                    error_msg = response['error'].get('message', str(response['error']))
                else:
                    error_msg = str(response['error'])
            
            flash(f"❌ Error: {error_msg}", "error")
            print(f"Full error response: {response}")
        
        return redirect("/create-template")
    
    except Exception as e:
        import traceback
        print(f"Exception traceback: {traceback.format_exc()}")
        flash(f"❌ Error creating template: {str(e)}", "error")
        return redirect("/create-template")


# ============================================================
# UTILITY ROUTES
# ============================================================

@app.route("/get-csv-columns", methods=["POST"])
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
def queue_stats():
    """Get current message queue statistics"""
    stats = message_queue.get_stats()
    return jsonify(stats)


@app.route("/queue-status")
def queue_status_page():
    """Render queue status monitoring page"""
    return render_template("queue_status.html")


# ============================================================
# SCHEDULED JOBS ROUTES
# ============================================================

@app.route("/scheduled-jobs")
def scheduled_jobs():
    """View scheduled jobs"""
    jobs = get_scheduled_jobs()
    return jsonify({"jobs": jobs})


@app.route("/cancel-job/<job_id>", methods=["POST"])
def cancel_scheduled_job(job_id):
    """Cancel a scheduled job"""
    success, message = cancel_job(job_id)
    return jsonify({"success": success, "message": message})


# ============================================================
# MAIN MESSAGE SENDING ROUTE
# ============================================================

@app.route("/", methods=["GET", "POST"])
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

        # Validate file size (5MB limit)
        csv_file.seek(0, os.SEEK_END)
        file_size = csv_file.tell()
        csv_file.seek(0)
        
        if file_size > 5 * 1024 * 1024:  # 5MB
            flash("❌ File too large. Maximum 5MB allowed.", "error")
            return redirect("/")

        # Read CSV
        try:
            df = pd.read_csv(csv_file)
        except Exception as e:
            flash(f"❌ Error reading CSV: {str(e)}", "error")
            return redirect("/")

        csv_columns = list(df.columns)

        # Validate required columns
        if "Phone" not in csv_columns:
            flash("CSV must contain a 'Phone' column.", "error")
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
            if not send_time:
                flash("Please enter a scheduled time.", "error")
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
                    send_time_str=send_time,
                    header_media_id=header_media_id  # Pass the image media ID
                )
            else:
                if not message_template:
                    flash("Please enter a message template.", "error")
                    return redirect("/")
                
                success, message = schedule_message_job(
                    df=df,
                    message_template=message_template,
                    send_time_str=send_time
                )
            
            if success:
                flash(f"✅ {message}", "success")
            else:
                flash(f"❌ {message}", "error")
            
            return redirect("/")

        # ==============================================================
        # IMMEDIATE SENDING (WITH RATE LIMITING)
        # ==============================================================
        
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

                # Add to queue instead of sending immediately
                message_queue.add_message(
                    send_template,
                    phone,
                    template_name,
                    params,
                    template_language,
                    header_media_id=header_media_id
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
                
                # Add to queue
                message_queue.add_message(
                    send_text,
                    phone,
                    personalized_msg
                )

            flash(f"✅ {len(df)} text messages queued for sending! Monitor progress at /queue-status", "success")
            return redirect("/")

    return render_template(
        "index.html",
        results=results,
        templates=templates,
        template_param_count=template_param_count,
        csv_columns=csv_columns
    )


# ============================================================
# GRACEFUL SHUTDOWN
# ============================================================

def cleanup():
    """Shutdown message queue gracefully"""
    print("\n🛑 Shutting down message queue...")
    message_queue.stop()
    print("✅ Cleanup complete")

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
        print("\n" + "="*50)
        print("🚀 Starting WhatsApp Bulk Sender")
        print("📊 Queue monitoring: http://localhost:5000/queue-status")
        print("📈 Queue stats API: http://localhost:5000/queue-stats")
        print("="*50 + "\n")
        
        app.run(debug=True, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\n🛑 Keyboard interrupt received")
        cleanup()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        cleanup()
        raise