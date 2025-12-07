import pandas as pd
import os
from datetime import datetime
from config import LOG_FILE

def log_message(name, phone, message, status, response):
    """Log message details to CSV file"""
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Determine status text
        status_text = "Success" if status in [200, 201] else "Failed"

        df_log = pd.DataFrame([
            {
                "Timestamp": now,
                "Name": name,
                "Phone": phone,
                "Message": message[:100] + "..." if len(message) > 100 else message,  # Truncate long messages
                "Status_Code": status,
                "Status": status_text,
                "Response": str(response)[:200],  # Truncate long responses
            }
        ])

        # Create directory if it doesn't exist
        log_dir = os.path.dirname(LOG_FILE)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # Append to CSV
        df_log.to_csv(
            LOG_FILE, 
            mode="a", 
            header=not os.path.exists(LOG_FILE), 
            index=False,
            encoding='utf-8'
        )
        
    except Exception as e:
        print(f"⚠️ Logging error: {e}")
        # Don't raise - logging failures shouldn't stop message sending