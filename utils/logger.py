import logging
import logging.handlers
import os
from datetime import datetime

from config import LOG_FILE

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()

_configured = False


def setup_logging():
    """Configure application-wide logging: rotating file + console."""
    global _configured
    if _configured:
        return
    _configured = True

    os.makedirs(LOG_DIR, exist_ok=True)

    fmt = logging.Formatter(
        '%(asctime)s [%(levelname)-8s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    root = logging.getLogger()
    root.handlers.clear()  # Remove any handlers Flask/werkzeug added before us

    root.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(LOG_DIR, 'app.log'),
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    # Keep third-party loggers quiet
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_message(name, phone, message, status, response):
    """Append a message send event to the CSV audit log."""
    _logger = logging.getLogger(__name__)
    try:
        import pandas as pd
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        status_text = 'Success' if status in [200, 201] else 'Failed'

        log_file = os.getenv('LOG_FILE_PATH', LOG_FILE)
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        df_log = pd.DataFrame([{
            'Timestamp': now,
            'Name': name,
            'Phone': phone,
            'Message': message[:100] + '...' if len(message) > 100 else message,
            'Status_Code': status,
            'Status': status_text,
            'Response': str(response)[:200],
        }])

        df_log.to_csv(
            log_file,
            mode='a',
            header=not os.path.exists(log_file),
            index=False,
            encoding='utf-8'
        )
    except Exception as e:
        _logger.warning(f'CSV log write failed: {e}')
