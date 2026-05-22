import os

bind = f"127.0.0.1:{os.getenv('PORT', '5000')}"

# 1 worker is correct here:
# - SQLite doesn't handle multiple processes writing simultaneously
# - Background scheduler threads must survive in the same process
workers = 1
worker_class = "gthread"
threads = 4

timeout = 120
graceful_timeout = 30
keepalive = 5
preload_app = True
# Disabled: worker recycling kills the in-memory message queue mid-campaign
max_requests = 0
max_requests_jitter = 0

_log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(_log_dir, exist_ok=True)
accesslog = os.path.join(_log_dir, "access.log")
errorlog  = os.path.join(_log_dir, "error.log")
loglevel  = os.getenv("LOG_LEVEL", "info").lower()

proc_name = "whatsapp-dashboard"
