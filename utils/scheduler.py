import time
from datetime import datetime, timedelta

def wait_until(send_time_str: str):
    """Block until HH:MM (24h format)."""
    now = datetime.now()
    hour, minute = map(int, send_time_str.split(":"))

    send_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if send_time <= now:
        send_time += timedelta(days=1)

    while datetime.now() < send_time:
        time.sleep(1)
