import pandas as pd
import os
from datetime import datetime
from config import LOG_FILE

def log_message(name, phone, message, status, response):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    df_log = pd.DataFrame([
        {
            "Timestamp": now,
            "Name": name,
            "Phone": phone,
            "Message": message,
            "Status": status,
            "Response": str(response),
        }
    ])

    df_log.to_csv(LOG_FILE, mode="a", header=not os.path.exists(LOG_FILE), index=False)
