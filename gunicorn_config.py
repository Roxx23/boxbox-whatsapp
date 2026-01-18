# Gunicorn configuration for Render.com free tier (512MB RAM)
import os
import multiprocessing

# Server socket
bind = f"0.0.0.0:{os.getenv('PORT', '10000')}"
backlog = 2048

# Worker processes
workers = 1  # Single worker to save memory
worker_class = 'gthread'  # Use threads instead of workers
threads = 2  # 2 threads per worker
worker_connections = 100
max_requests = 1000
max_requests_jitter = 50

# Timeouts
timeout = 300
graceful_timeout = 120
keepalive = 5

# Memory optimization
preload_app = True  # Load app before forking workers
max_requests = 1000  # Restart workers after 1000 requests to prevent memory leaks

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'whatsapp-dashboard'

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (handled by Render)
keyfile = None
certfile = None
