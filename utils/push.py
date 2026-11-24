"""Web Push (browser notifications) for incoming WhatsApp messages.

Keys come from .env (generate them once with scripts/generate_vapid_keys.py):
    VAPID_PUBLIC_KEY   base64url uncompressed P-256 point (given to browsers)
    VAPID_PRIVATE_KEY  base64url raw 32-byte private key (server only)
    VAPID_SUBJECT      mailto:hello@boxbox.in

Without both keys push is off: is_configured() is False, the dashboard hides
the toggle and nothing is sent. Sends always run in a daemon thread so the
WhatsApp webhook never waits on, or fails because of, a push service.
Never log keys or full subscription endpoints (the endpoint is a bearer URL).
"""
import json
import logging
import os
import threading
from collections import OrderedDict

logger = logging.getLogger(__name__)

PREVIEW_CHARS = 80
PUSH_TTL = 24 * 3600      # push service keeps an undelivered notification for a day
PUSH_TIMEOUT = 10         # seconds per push service request

_vapid = None             # parsed private key, built once
_vapid_lock = threading.Lock()
_seen_ids = OrderedDict() # WhatsApp message ids already pushed (Meta retries webhooks)
_seen_lock = threading.Lock()
_SEEN_MAX = 500


def public_key():
    return (os.getenv('VAPID_PUBLIC_KEY') or '').strip()


def is_configured():
    return bool(public_key() and (os.getenv('VAPID_PRIVATE_KEY') or '').strip())


def _subject():
    return (os.getenv('VAPID_SUBJECT') or 'mailto:hello@boxbox.in').strip()


def _get_vapid():
    global _vapid
    with _vapid_lock:
        if _vapid is None:
            from py_vapid import Vapid
            _vapid = Vapid.from_string(private_key=os.getenv('VAPID_PRIVATE_KEY').strip())
        return _vapid


def _short_endpoint(endpoint):
    """Host plus the last few characters: enough to tell devices apart in logs."""
    try:
        from urllib.parse import urlparse
        return f"{urlparse(endpoint).netloc}/…{endpoint[-6:]}"
    except Exception:
        return '…'


def build_message_payload(phone, text, name=None, unread=None):
    """Notification JSON for one incoming message. Clicking opens the thread."""
    who = (name or '').strip() or phone
    body = (text or '').strip() or 'New message'
    if len(body) > PREVIEW_CHARS:
        body = body[:PREVIEW_CHARS - 1].rstrip() + '…'
    return {
        'title': who,
        'body': body,
        'url': '/inbox/' + (phone or '').lstrip('+'),
        'tag': 'inbox-' + (phone or '').lstrip('+'),  # one notification per customer, newest wins
        'unread': unread,
    }


def send_to_user(db, user_id, payload):
    """Send payload to every subscribed device of user_id (blocking).
    A 404/410 from the push service means the subscription is gone: delete it.
    Returns (sent, removed, failed)."""
    if not is_configured():
        return 0, 0, 0
    from pywebpush import webpush, WebPushException
    data = json.dumps(payload)
    sent = removed = failed = 0
    for sub in db.get_push_subscriptions(user_id):
        info = {'endpoint': sub['endpoint'], 'keys': {'p256dh': sub['p256dh'], 'auth': sub['auth']}}
        try:
            webpush(info, data=data, vapid_private_key=_get_vapid(),
                    vapid_claims={'sub': _subject()},  # fresh dict: webpush fills aud/exp per endpoint
                    ttl=PUSH_TTL, timeout=PUSH_TIMEOUT)
            sent += 1
            db.touch_push_subscription(sub['endpoint'])
        except WebPushException as e:
            code = getattr(getattr(e, 'response', None), 'status_code', None)
            if code in (404, 410):
                db.delete_push_subscription(sub['endpoint'])
                removed += 1
                logger.info(f"Push subscription expired ({code}), removed: {_short_endpoint(sub['endpoint'])}")
            else:
                failed += 1
                logger.warning(f"Push failed (HTTP {code}) for {_short_endpoint(sub['endpoint'])}")
        except Exception as e:
            failed += 1
            logger.warning(f"Push error for {_short_endpoint(sub['endpoint'])}: {type(e).__name__}")
    return sent, removed, failed


def _already_pushed(message_id):
    if not message_id:
        return False
    with _seen_lock:
        if message_id in _seen_ids:
            return True
        _seen_ids[message_id] = True
        while len(_seen_ids) > _SEEN_MAX:
            _seen_ids.popitem(last=False)
        return False


def notify_incoming_message(db, user_id, phone, text, message_id=None, profile_name=None):
    """Fire-and-forget push for one inbound WhatsApp message. Never raises."""
    try:
        if not is_configured() or not user_id or not phone or _already_pushed(message_id):
            return
        threading.Thread(target=_notify_worker, name='push-notify', daemon=True,
                         args=(db, user_id, phone, text, profile_name)).start()
    except Exception as e:
        logger.warning(f"Could not start push thread: {type(e).__name__}")


def _notify_worker(db, user_id, phone, text, profile_name):
    try:
        name = None
        try:
            c = db.get_customer_by_phone(phone)
            if c:
                name = f"{c.get('first_name') or ''} {c.get('last_name') or ''}".strip() or None
        except Exception:
            pass
        name = name or profile_name
        unread = None
        try:
            unread = db.count_unread_inbox_conversations(user_id)
        except Exception:
            pass
        sent, removed, failed = send_to_user(db, user_id, build_message_payload(phone, text, name, unread))
        if sent or removed or failed:
            logger.info(f"Push for incoming message: sent {sent}, removed {removed}, failed {failed}")
    except Exception as e:
        logger.warning(f"Push notify failed: {type(e).__name__}: {e}")
