import time
from datetime import datetime, timedelta

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