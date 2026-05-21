import logging
import time
import threading
from datetime import datetime, timedelta
from utils.whatsapp import send_text, send_template, get_templates

logger = logging.getLogger(__name__)

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
jobs_lock = threading.Lock()  # Thread safety for job modifications
job_id_counter = 0

# Global reference to message_queue (will be set by app.py)
_message_queue = None
_waba_id = None

def set_message_queue(queue):
    """Called by app.py to set the message queue reference"""
    global _message_queue
    _message_queue = queue
    logger.info("Background scheduler connected to message queue")

def set_waba_id(waba_id):
    """Called by app.py to set the WABA ID"""
    global _waba_id
    _waba_id = waba_id
    logger.info(f"Background scheduler using WABA ID: {waba_id}")


def wait_until(send_time_str: str):
    """Block until specified date and time.
    
    Supports two formats:
    - HH:MM (24h format) - for same day or next day
    - YYYY-MM-DD HH:MM - for specific date and time
    """
    try:
        now = datetime.now()
        
        # Check if it's a full datetime or just time
        if " " in send_time_str:
            # Full datetime format: "YYYY-MM-DD HH:MM"
            try:
                send_time = datetime.strptime(send_time_str, "%Y-%m-%d %H:%M")
            except ValueError:
                raise ValueError("Invalid datetime format. Use YYYY-MM-DD HH:MM")
            
            if send_time <= now:
                raise ValueError("Scheduled time must be in the future")
                
        else:
            # Just time format: "HH:MM"
            hour, minute = map(int, send_time_str.split(":"))
            
            # Validate time format
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError("Invalid time format. Use HH:MM (00:00 to 23:59)")

            send_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

            if send_time <= now:
                send_time += timedelta(days=1)
                logger.info(f"Scheduled for tomorrow at {send_time_str}")
            else:
                logger.info(f"Scheduled for today at {send_time_str}")

        wait_seconds = (send_time - now).total_seconds()
        days = int(wait_seconds // 86400)
        hours = int((wait_seconds % 86400) // 3600)
        minutes = int((wait_seconds % 3600) // 60)

        if days > 0:
            time_msg = f"{days} day(s), {hours} hour(s), {minutes} minute(s)"
        elif hours > 0:
            time_msg = f"{hours} hour(s), {minutes} minute(s)"
        else:
            time_msg = f"{minutes} minute(s)"

        logger.info(f"Waiting {time_msg} until {send_time.strftime('%Y-%m-%d %H:%M:%S')}")

        while datetime.now() < send_time:
            time.sleep(60)

        logger.info("Scheduled time reached — starting to send messages")

    except ValueError as e:
        logger.error(f"Invalid schedule time: {e}")
        raise


def check_template_needs_image(template_name):
    """
    Check if a template requires an IMAGE header
    Returns: (needs_image: bool, template_language: str)
    """
    if not _waba_id:
        logger.warning("WABA_ID not set in scheduler")
        return False, "en"
    
    templates = get_templates(_waba_id)
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
                         send_time_str=None, header_media_id=None, button_params=None,
                         user_id=None, username=None):
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
        button_params: Dict with button parameters (e.g., {"copy_code": "SAVE20"})
        user_id: User ID for tracking
        username: Username for tracking
    """
    global job_id_counter, scheduled_jobs
    
    # Debug: Print what button_params we received
    logger.debug(f"schedule_message_job called with button_params: {button_params}")
    
    job_id_counter += 1
    job_id = f"job_{job_id_counter}"
    
    # Validate
    if not send_time_str:
        return False, "Send time is required"
    
    if not _waba_id:
        return False, "WABA_ID not configured in scheduler"
    
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
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'button_params': button_params  # Store button params with job
    }
    
    # Thread-safe job addition
    with jobs_lock:
        scheduled_jobs.append(job_info)
    
    # Create campaign record immediately when scheduled
    campaign_id = None
    if user_id:
        try:
            from utils.database import Database
            db = Database()
            
            campaign_name = f"Scheduled Campaign {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            campaign_type = 'Template' if template_name else 'Text'
            
            # Create campaign with 'scheduled' status
            campaign_id = db.create_campaign(
                user_id=user_id,
                username=username or 'System',
                campaign_name=campaign_name,
                campaign_type=campaign_type,
                template_name=template_name,
                recipient_count=len(df),
                scheduled_time=send_time_str
            )
            db.update_campaign_status(campaign_id, 'scheduled')
            
            # Store campaign_id in job_info
            job_info['campaign_id'] = campaign_id
            
            # Log scheduling activity
            message_type = f"Template ({template_name})" if template_name else "Text Message"
            db.log_activity(
                user_id=user_id,
                username=username or 'System',
                action='Message Scheduled',
                details=f"Scheduled {len(df)} {message_type} messages for {send_time_str}",
                ip_address='127.0.0.1'
            )
        except Exception as e:
            logger.error(f"Failed to create campaign or log scheduling activity: {e}")
    
    # Start background thread
    def job_worker():
        # Get data from job_info
        campaign_id = job_info.get('campaign_id')
        stored_button_params = job_info.get('button_params')
        
        # Debug: Check if button_params is accessible
        logger.debug(f"Scheduler worker starting with button_params: {stored_button_params}")
        
        try:
            # Update status
            job_info['status'] = 'waiting'
            
            # Wait until scheduled time
            wait_until(send_time_str)
            
            # Update campaign to running when execution starts
            if user_id and campaign_id:
                from utils.database import Database
                db = Database()
                
                db.update_campaign_status(campaign_id, 'running')
                
                # Log campaign start
                campaign = db.get_campaign(campaign_id)
                campaign_name = campaign.get('campaign_name', 'Scheduled Campaign')
                campaign_type = campaign.get('campaign_type', 'Unknown')
                
                db.log_activity(
                    user_id=user_id,
                    username=username or 'System',
                    action='Scheduled Campaign Started',
                    details=f"Campaign: {campaign_name}, Recipients: {len(df)}, Type: {campaign_type}",
                    ip_address='127.0.0.1'
                )
            
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
                    name = row_dict.get("Name", "")
                    
                    # Build parameters
                    params = []
                    for col_name in template_params_mapping:
                        val = row_dict.get(col_name)
                        if val is None:
                            logger.warning(f"Column '{col_name}' missing for {phone}")
                            continue
                        params.append(str(val))
                    
                    # Create message record in database
                    message_id = None
                    if user_id and campaign_id:
                        try:
                            from utils.database import Database
                            db = Database()
                            message_id = db.add_message(
                                campaign_id=campaign_id,
                                user_id=user_id,
                                phone_number=phone,
                                recipient_name=name,
                                message_content=f"Template: {template_name}",
                                template_name=template_name,
                                status='queued'
                            )
                        except Exception as e:
                            logger.error(f"Error creating message record: {e}")
                    
                    # Send with queue if available, otherwise send directly
                    if message_queue:
                        message_queue.add_message(
                            send_template,
                            phone,
                            template_name,
                            params,
                            template_language,
                            header_media_id=header_media_id,
                            button_params=stored_button_params,
                            user_id=user_id,
                            username=username,
                            campaign_id=campaign_id,
                            message_id=message_id
                        )
                    else:
                        # Send directly without queue
                        logger.warning("Message queue not available, sending directly")
                        send_template(
                            phone,
                            template_name,
                            params,
                            template_language,
                            header_media_id=header_media_id,
                            button_params=stored_button_params
                        )
                        time.sleep(1)  # Basic rate limiting
                    
                logger.info(f"Completed scheduled batch: template='{template_name}', count={len(df)}")
            
            else:
                # Free text messages
                for idx, row in df.iterrows():
                    row_dict = row.to_dict()
                    phone = str(row_dict.get("Phone")).strip()
                    name = row_dict.get("Name", "")
                    
                    personalized_msg = personalize(message_template, row_dict, idx + 1)
                    
                    # Create message record in database
                    message_id = None
                    if user_id and campaign_id:
                        try:
                            from utils.database import Database
                            db = Database()
                            message_id = db.add_message(
                                campaign_id=campaign_id,
                                user_id=user_id,
                                phone_number=phone,
                                recipient_name=name,
                                message_content=personalized_msg,
                                status='queued'
                            )
                        except Exception as e:
                            logger.error(f"Error creating message record: {e}")
                    
                    if message_queue:
                        message_queue.add_message(
                            send_text,
                            phone,
                            personalized_msg,
                            user_id=user_id,
                            username=username,
                            campaign_id=campaign_id,
                            message_id=message_id
                        )
                    else:
                        logger.warning("Message queue not available, sending directly")
                        send_text(phone, personalized_msg)
                        time.sleep(1)
                
                logger.info(f"Completed scheduled batch: text messages, count={len(df)}")
            
            # Update status
            job_info['status'] = 'completed'
            job_info['completed_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Log completion
            if user_id:
                try:
                    from utils.database import Database
                    db = Database()
                    
                    message_type = f"Template ({template_name})" if template_name else "Text"
                    db.log_activity(
                        user_id=user_id,
                        username=username or 'System',
                        action='Scheduled Campaign Completed',
                        details=f"Completed sending {len(df)} {message_type} messages",
                        ip_address='127.0.0.1'
                    )
                except Exception as log_error:
                    logger.warning(f"Failed to log completion: {log_error}")
            
        except Exception as e:
            logger.exception(f"Scheduled job error: {e}")
            job_info['status'] = 'failed'
            job_info['error'] = str(e)
            
            # Log failure
            if user_id:
                try:
                    from utils.database import Database
                    db = Database()
                    
                    message_type = f"Template ({template_name})" if template_name else "Text"
                    db.log_activity(
                        user_id=user_id,
                        username=username or 'System',
                        action='Scheduled Campaign Failed',
                        details=f"Failed to send {len(df)} {message_type} messages: {str(e)}",
                        ip_address='127.0.0.1'
                    )
                except Exception as log_error:
                    logger.warning(f"Failed to log failure: {log_error}")
    
    thread = threading.Thread(target=job_worker, daemon=True)
    thread.start()
    
    return True, f"Messages scheduled for {send_time_str} (Job ID: {job_id})"


def get_scheduled_jobs():
    """Return list of all scheduled jobs"""
    return scheduled_jobs


def cancel_job(job_id):
    """Cancel a scheduled job (thread-safe)"""
    global scheduled_jobs
    
    with jobs_lock:
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