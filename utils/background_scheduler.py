from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timedelta
import pandas as pd
from utils.whatsapp import send_text, send_template
from utils.logger import log_message
from utils.personalize import personalize

# Initialize background scheduler
scheduler = BackgroundScheduler()
scheduler.start()

def schedule_message_job(
    df,
    template_name=None,
    template_language="en",
    template_params_mapping=None,
    message_template=None,
    send_time_str=None
):
    """Schedule messages to be sent at a specific time"""
    
    # Parse send time
    now = datetime.now()
    hour, minute = map(int, send_time_str.split(":"))
    
    send_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    # If time has passed today, DON'T schedule for tomorrow - show error
    if send_time <= now:
        return False, "Selected time has already passed today. Please choose a future time."
    
    # Schedule the job
    job_id = f"bulk_send_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    if template_name:
        # Schedule template messages
        scheduler.add_job(
            func=send_template_messages,
            trigger=DateTrigger(run_date=send_time),
            args=[df, template_name, template_language, template_params_mapping],
            id=job_id,
            replace_existing=True
        )
    else:
        # Schedule text messages
        scheduler.add_job(
            func=send_text_messages,
            trigger=DateTrigger(run_date=send_time),
            args=[df, message_template],
            id=job_id,
            replace_existing=True
        )
    
    return True, f"Messages scheduled for {send_time.strftime('%I:%M %p')} today. Job ID: {job_id}"


def send_template_messages(df, template_name, template_language, params_mapping):
    """Background task to send template messages"""
    print(f"🚀 Starting scheduled template message batch: {template_name}")
    
    for idx, row in df.iterrows():
        row_dict = row.to_dict()
        name = row_dict.get("Name", "")
        phone = str(row_dict.get("Phone"))
        
        # Build parameters
        params = []
        for col in params_mapping:
            val = row_dict.get(col)
            params.append(str(val) if val is not None else "")
        
        # Send message
        status, resp = send_template(phone, template_name, params, template_language)
        
        # Log
        log_message(name, phone, f"TEMPLATE: {template_name} → {params}", status, resp)
        
        # Small delay to avoid rate limits
        import time
        time.sleep(1)
    
    print(f"✅ Completed scheduled batch: {template_name} ({len(df)} messages)")


def send_text_messages(df, message_template):
    """Background task to send text messages"""
    print(f"🚀 Starting scheduled text message batch")
    
    for idx, row in df.iterrows():
        row_dict = row.to_dict()
        name = row_dict.get("Name", "")
        phone = str(row_dict.get("Phone")).strip()
        
        # Personalize message
        personalized_msg = personalize(message_template, row_dict, idx + 1)
        
        # Send message
        status, resp = send_text(phone, personalized_msg)
        
        # Log
        log_message(name, phone, personalized_msg, status, resp)
        
        # Small delay to avoid rate limits
        import time
        time.sleep(1)
    
    print(f"✅ Completed scheduled batch ({len(df)} messages)")


def get_scheduled_jobs():
    """Get list of all scheduled jobs"""
    jobs = scheduler.get_jobs()
    job_list = []
    
    for job in jobs:
        job_list.append({
            "id": job.id,
            "next_run": job.next_run_time.strftime("%Y-%m-%d %I:%M %p") if job.next_run_time else "N/A",
            "function": job.func.__name__
        })
    
    return job_list


def cancel_job(job_id):
    """Cancel a scheduled job"""
    try:
        scheduler.remove_job(job_id)
        return True, f"Job {job_id} cancelled successfully"
    except:
        return False, f"Job {job_id} not found"