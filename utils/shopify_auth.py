"""Single source of the Shopify Admin API access token.

Two ways to authenticate, chosen by what is in the environment:

1. SHOPIFY_CLIENT_ID + SHOPIFY_CLIENT_SECRET set (Dev Dashboard app):
   the token comes from Shopify's client-credentials grant
   (POST https://<shop>.myshopify.com/admin/oauth/access_token) and expires
   after ~24h. It is cached in memory, shared by every thread, and renewed
   when less than REFRESH_MARGIN_SECONDS of life remain. Any 401 from the
   Admin API forces one renewal and one retry (see shopify_request).
2. Otherwise: the static SHOPIFY_ACCESS_TOKEN (old custom-app token).

If the grant fails, a still-unexpired cached token keeps being used, and
after that the static SHOPIFY_ACCESS_TOKEN (if any) is the last resort.

Never log the token or the client secret.
"""
import logging
import os
import threading
import time

import requests

logger = logging.getLogger(__name__)

API_VERSION = '2025-10'
REFRESH_MARGIN_SECONDS = 3600      # renew when under 1h of life is left
GRANT_TIMEOUT_SECONDS = 15
GRANT_BACKOFF_SECONDS = 60       # after a failed grant, don't try again for this long
DEFAULT_LIFETIME_SECONDS = 86399   # what Shopify returns today; used if expires_in is missing

_lock = threading.Lock()
_cache = {'token': None, 'expires_at': 0.0, 'client_id': None, 'grant_failed_at': 0.0}


def _env(name):
    return (os.getenv(name) or '').strip()


def shop_name():
    return _env('SHOPIFY_SHOP_NAME')


def uses_client_credentials():
    return bool(_env('SHOPIFY_CLIENT_ID') and _env('SHOPIFY_CLIENT_SECRET'))


def is_configured():
    """True when a shop is set and at least one way to get a token exists."""
    return bool(shop_name() and (uses_client_credentials() or _env('SHOPIFY_ACCESS_TOKEN')))


def admin_base_url():
    return f"https://{shop_name()}.myshopify.com/admin/api/{API_VERSION}"


def _request_grant_token():
    """Run the client-credentials grant. Returns (token, expires_at) or (None, 0)."""
    shop = shop_name()
    if not shop:
        logger.error("Shopify token grant skipped: SHOPIFY_SHOP_NAME not set")
        return None, 0.0
    url = f"https://{shop}.myshopify.com/admin/oauth/access_token"
    try:
        resp = requests.post(url, data={
            'grant_type': 'client_credentials',
            'client_id': _env('SHOPIFY_CLIENT_ID'),
            'client_secret': _env('SHOPIFY_CLIENT_SECRET'),
        }, timeout=GRANT_TIMEOUT_SECONDS)
    except requests.RequestException as e:
        logger.error(f"Shopify token grant failed: {type(e).__name__}")
        return None, 0.0
    if resp.status_code != 200:
        # The body of an error response carries no secrets, but keep it short.
        logger.error(f"Shopify token grant returned {resp.status_code}: {resp.text[:200]}")
        return None, 0.0
    try:
        data = resp.json()
        token = data['access_token']
    except (ValueError, KeyError, TypeError):
        logger.error("Shopify token grant returned 200 without an access_token")
        return None, 0.0
    try:
        lifetime = float(data.get('expires_in') or DEFAULT_LIFETIME_SECONDS)
    except (TypeError, ValueError):
        lifetime = DEFAULT_LIFETIME_SECONDS
    logger.info(f"Shopify access token renewed via client credentials "
                f"(valid {int(lifetime // 3600)}h, scope: {data.get('scope', '?')})")
    return token, time.time() + lifetime


def get_shopify_token(force_refresh=False, stale_token=None):
    """Return a usable Admin API token, or '' if none can be had.

    Thread-safe: concurrent callers share one cached token and at most one
    grant request is in flight at a time.

    force_refresh + stale_token (the token that just got a 401): renew only if
    the cache still holds that same token; if another thread already replaced
    it, the replacement is returned without a second grant.

    After a failed grant, no new grant is attempted for GRANT_BACKOFF_SECONDS
    (callers get the cached-but-unexpired or static token instead), so a
    Shopify outage or bad secret can't make every call wait on the grant
    timeout under the lock -- e.g. stalling an order webhook past Shopify's 5s.
    """
    if not uses_client_credentials():
        return _env('SHOPIFY_ACCESS_TOKEN')

    client_id = _env('SHOPIFY_CLIENT_ID')

    def _fresh(now):
        return (c['token'] and c['client_id'] == client_id
                and c['expires_at'] - now > REFRESH_MARGIN_SECONDS)

    c = _cache
    if not force_refresh and _fresh(time.time()):
        return c['token']

    with _lock:
        now = time.time()
        if not force_refresh and _fresh(now):
            return c['token']          # another thread renewed it while we waited
        if (force_refresh and stale_token and c['token'] and c['token'] != stale_token
                and c['client_id'] == client_id and c['expires_at'] > now):
            return c['token']          # another thread already replaced the 401'd token
        if now - c['grant_failed_at'] >= GRANT_BACKOFF_SECONDS:
            token, expires_at = _request_grant_token()
            if token:
                c.update(token=token, expires_at=expires_at, client_id=client_id, grant_failed_at=0.0)
                return token
            c['grant_failed_at'] = now
        if c['token'] and c['client_id'] == client_id and c['expires_at'] > now and c['token'] != stale_token:
            logger.warning("Shopify token renewal unavailable; using the cached token until it expires")
            return c['token']
        fallback = _env('SHOPIFY_ACCESS_TOKEN')
        if fallback:
            logger.warning("Shopify token renewal unavailable; falling back to static SHOPIFY_ACCESS_TOKEN")
        return fallback


def _token_for_retry(used_token):
    """After a 401: renew once, unless another thread already replaced the token."""
    return get_shopify_token(force_refresh=True, stale_token=used_token)


def shopify_request(method, url_or_path, headers=None, timeout=30, **kwargs):
    """requests.request() against the Admin API with the current token.

    `url_or_path` is a full URL (e.g. a pagination Link) or a path relative to
    admin_base_url() such as '/products/123.json'. On a 401 with
    client credentials, the token is renewed once and the call retried once.
    Returns the requests.Response (or raises requests exceptions, as before).
    """
    url = url_or_path if url_or_path.startswith('http') else admin_base_url() + url_or_path
    token = get_shopify_token()
    hdrs = {'Content-Type': 'application/json', **(headers or {}), 'X-Shopify-Access-Token': token}
    resp = requests.request(method, url, headers=hdrs, timeout=timeout, **kwargs)
    if resp.status_code == 401 and uses_client_credentials():
        logger.warning(f"Shopify Admin API returned 401; renewing token and retrying once")
        new_token = _token_for_retry(token)
        if new_token and new_token != token:
            hdrs['X-Shopify-Access-Token'] = new_token
            resp = requests.request(method, url, headers=hdrs, timeout=timeout, **kwargs)
    return resp


def _reset_cache_for_tests():
    with _lock:
        _cache.update(token=None, expires_at=0.0, client_id=None, grant_failed_at=0.0)
