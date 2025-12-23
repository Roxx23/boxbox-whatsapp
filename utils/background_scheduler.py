import time
import threading
from datetime import datetime, timedelta
from utils.whatsapp import send_text, send_template, get_templates

# Import personalize if you have it
try:
    from utils.personalize import personalize
except ImportError:
    def personalize(template, row_dict, idx):
        """Fallback personalize function"""
        result = template
        for key, value in row_dict.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result

# Global storage for scheduled jobs
scheduled_jobs = []
job_id_counter = 0

# Global reference to message_queue (will be set by app.py)
_message_queue = None

def set_message_queue(queue):
    """Called by app.py to set the message queue reference"""
    global _message_queue
    _message_queue = queue
    print("✅ Background scheduler connected to message queue")


# WABA_ID should be imported from your config
WABA_ID = "2252354741929132"


def wait_until(send_time_str: str):
    """Block until HH:MM (24h format)."""
    try:
        now = datetime.now()
        hour, minute = map(int, send_time_str.split(":"))
        
        # Validate time format
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("Invalid time format. Use HH:MM (00:00 to 23:59)")

        send_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        if send_time <= now:
            send_time += timedelta(days=1)
            print(f"⏰ Scheduled for tomorrow at {send_time_str}")
        else:
            print(f"⏰ Scheduled for today at {send_time_str}")

        wait_seconds = (send_time - now).total_seconds()
        print(f"⏳ Waiting {int(wait_seconds)} seconds until {send_time.strftime('%Y-%m-%d %H:%M:%S')}")

        while datetime.now() < send_time:
            time.sleep(1)
        
        print("✅ Time reached! Starting to send messages...")
        
    except ValueError as e:
        print(f"❌ Error: {e}")
        raise


def check_template_needs_image(template_name):
    """
    Check if a template requires an IMAGE header
    Returns: (needs_image: bool, template_language: str)
    """
    templates = get_templates(WABA_ID)
    selected_template = next((t for t in templates if t["name"] == template_name), None)
    
    if not selected_template:
        return False, "en"
    
    template_language = selected_template.get("language", "en")
    
    # Check for IMAGE header
    header_component = next(
        (c for c in selected_template["components"] if c["type"] == "HEADER"),
        None
    )
    
    needs_image = header_component and header_component.get("format") == "IMAGE"
    
    return needs_image, template_language


def schedule_message_job(df, template_name=None, template_language="en", 
                         template_params_mapping=None, message_template=None, 
                         send_time_str=None, header_media_id=None):
    """
    Schedule a message sending job
    
    Args:
        df: DataFrame with contacts
        template_name: WhatsApp template name (if using template)
        template_language: Template language code
        template_params_mapping: List of column names for template parameters
        message_template: Free text message (if not using template)
        send_time_str: Time to send (HH:MM format)
        header_media_id: Media ID for image header (if template needs it)
    """
    global job_id_counter, scheduled_jobs
    
    job_id_counter += 1
    job_id = f"job_{job_id_counter}"
    
    # Validate
    if not send_time_str:
        return False, "Send time is required"
    
    # Check if template needs image
    if template_name:
        needs_image, detected_language = check_template_needs_image(template_name)
        
        if needs_image and not header_media_id:
            return False, f"Template '{template_name}' requires an IMAGE header. Please upload an image."
        
        # Use detected language if not provided
        if template_language == "en":
            template_language = detected_language
    
    # Create job info
    job_info = {
        'job_id': job_id,
        'scheduled_time': send_time_str,
        'status': 'pending',
        'template_name': template_name,
        'message_template': message_template,
        'contact_count': len(df),
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    scheduled_jobs.append(job_info)
    
    # Start background thread
    def job_worker():
        try:
            # Update status
            job_info['status'] = 'waiting'
            
            # Wait until scheduled time
            wait_until(send_time_str)
            
            # Update status
            job_info['status'] = 'sending'
            
            # Use the global message_queue reference (set by app.py)
            message_queue = _message_queue
            
            # Send messages
            if template_name:
                # Template messages
                for idx, row in df.iterrows():
                    row_dict = row.to_dict()
                    phone = str(row_dict.get("Phone"))
                    
                    # Build parameters
                    params = []
                    for col_name in template_params_mapping:
                        val = row_dict.get(col_name)
                        if val is None:
                            print(f"⚠️ Column '{col_name}' missing for {phone}")
                            continue
                        params.append(str(val))
                    
                    # Send with queue if available, otherwise send directly
                    if message_queue:
                        message_queue.add_message(
                            send_template,
                            phone,
                            template_name,
                            params,
                            template_language,
                            header_media_id=header_media_id
                        )
                    else:
                        # Send directly without queue
                        print("⚠️ Message queue not available, sending directly")
                        send_template(
                            phone,
                            template_name,
                            params,
                            template_language,
                            header_media_id=header_media_id
                        )
                        time.sleep(1)  # Basic rate limiting
                    
                print(f"✅ Completed scheduled batch: {template_name} ({len(df)} messages)")
            
            else:
                # Free text messages
                for idx, row in df.iterrows():
                    row_dict = row.to_dict()
                    phone = str(row_dict.get("Phone")).strip()
                    
                    personalized_msg = personalize(message_template, row_dict, idx + 1)
                    
                    if message_queue:
                        message_queue.add_message(send_text, phone, personalized_msg)
                    else:
                        print("⚠️ Message queue not available, sending directly")
                        send_text(phone, personalized_msg)
                        time.sleep(1)
                
                print(f"✅ Completed scheduled batch: text messages ({len(df)} messages)")
            
            # Update status
            job_info['status'] = 'completed'
            job_info['completed_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
        except Exception as e:
            print(f"❌ Scheduled job error: {e}")
            import traceback
            traceback.print_exc()
            job_info['status'] = 'failed'
            job_info['error'] = str(e)
    
    thread = threading.Thread(target=job_worker, daemon=True)
    thread.start()
    
    return True, f"Messages scheduled for {send_time_str} (Job ID: {job_id})"


def get_scheduled_jobs():
    """Return list of all scheduled jobs"""
    return scheduled_jobs


def cancel_job(job_id):
    """Cancel a scheduled job"""
    global scheduled_jobs
    
    job = next((j for j in scheduled_jobs if j['job_id'] == job_id), None)
    
    if not job:
        return False, "Job not found"
    
    if job['status'] in ['completed', 'failed']:
        return False, f"Cannot cancel {job['status']} job"
    
    if job['status'] == 'sending':
        return False, "Cannot cancel job that is already sending"
    
    job['status'] = 'cancelled'
    job['cancelled_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    return True, f"Job {job_id} cancelled successfully"