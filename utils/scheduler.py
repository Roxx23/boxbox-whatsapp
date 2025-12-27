import time
from datetime import datetime, timedelta

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
                print(f"⏰ Scheduled for tomorrow at {send_time_str}")
            else:
                print(f"⏰ Scheduled for today at {send_time_str}")

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
        
        print(f"⏳ Waiting {time_msg} until {send_time.strftime('%Y-%m-%d %H:%M:%S')}")

        while datetime.now() < send_time:
            time.sleep(60)  # Check every minute instead of every second
        
        print("✅ Time reached! Starting to send messages...")
        
    except ValueError as e:
        print(f"❌ Error: {e}")
        raise