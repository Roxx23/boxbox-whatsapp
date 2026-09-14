# WhatsApp Dashboard — Project Context

## What This Is

A Flask web app for sending WhatsApp marketing campaigns to Shopify customers.
Owner: Abhi (hello@boxbox.in) — single-user, registration is closed.

Live URL: https://internal.boxbox.in (migrated from dashboard.boxbox.in -- see Deployment section)

---

## Tech Stack

- **Backend**: Python 3 / Flask
- **Database**: SQLite (`whatsapp_dashboard.db`) — kept intentionally over PostgreSQL (single server, 1 gunicorn worker, no concurrent write issues)
- **Queue**: In-memory `MessageQueue` (utils/rate_limiter.py) — messages are lost on restart
- **Auth**: Flask-Login + bcrypt, users stored in `users.json`
- **Server**: GCP (migrated from AWS Lightsail -- exact instance type/region/OS not yet confirmed in this doc; update once known)
- **Process manager**: systemd (`whatsapp-dashboard.service`)
- **Reverse proxy**: Nginx → gunicorn on 127.0.0.1:5000
- **SSL**: Let's Encrypt via certbot
- **Timezone**: IST (Asia/Kolkata) — set with `sudo timedatectl set-timezone Asia/Kolkata`

---

## Project Structure

```
app.py                        # Main Flask app, all routes
config.py                     # Loads .env vars
gunicorn_config.py            # Gunicorn production config
requirements.txt
deploy/
  setup.sh                    # One-time server setup script
  deploy.sh                   # Pull latest + restart (run on server)
utils/
  database.py                 # All SQLite operations
  auth.py                     # UserManager + User model
  whatsapp.py                 # WhatsApp Cloud API calls
  rate_limiter.py             # RateLimiter + MessageQueue (in-memory queue)
  background_scheduler.py     # Scheduled campaign threading
  logger.py                   # setup_logging() + RotatingFileHandler
  shopify_integration.py      # Shopify customer sync
  personalize.py              # Template variable substitution
templates/
  base.html                   # Dark/gold theme base layout
  index.html                  # Campaign send page
  customers.html              # Customer list + segments
  campaign_details.html       # Per-campaign message stats
  campaigns.html              # Campaign list
  analytics.html              # Dashboard analytics
  automation.html             # Automation settings page (NEW)
  login.html                  # Login only (signup disabled)
  ...
```

---

## Environment Variables (.env on server)

```
WHATSAPP_ACCESS_TOKEN=...
WHATSAPP_PHONE_NUMBER_ID=...
WABA_ID=...
WEBHOOK_VERIFY_TOKEN=my_secret_webhook_token_2024
SECRET_KEY=...
SHOPIFY_SHOP_NAME=...          # just the store name, e.g. "boxbox" (not .myshopify.com)
SHOPIFY_ACCESS_TOKEN=...       # needs read_customers scope; read_products for product images
SHOPIFY_WEBHOOK_SECRET=...     # optional — if set, verifies Shopify webhook HMAC signatures
```

Location on server: `/home/ubuntu/whatsapp-dashboard/.env`

---

## Gunicorn Config (gunicorn_config.py) — Critical Settings

```python
workers = 1          # MUST stay 1 — SQLite can't handle multiple writers
worker_class = "gthread"
threads = 4
preload_app = False  # MUST be False — True kills background threads after fork
max_requests = 0     # MUST be 0 — non-zero causes worker recycle mid-campaign, wiping the in-memory queue
max_requests_jitter = 0
```

**Why `preload_app = False`**: With `True`, gunicorn forks after loading the app. Python threads don't survive fork, so the `MessageQueue` worker thread dies. Messages queue up (`pending` grows) but nothing processes them (`total_processed` stays 0).

**Why `max_requests = 0`**: WhatsApp webhooks count as HTTP requests. A 1000-message campaign generates ~2000 webhook events. With `max_requests = 500`, the worker recycled after ~200 messages sent, wiping the queue.

---

## Deployment

### Server details
- **Provider**: GCP (migrated from AWS Lightsail as of 2026-09-14)
- **Domain**: `internal.boxbox.in` (subdomain of boxbox.in, replaces `dashboard.boxbox.in` -- publicly reachable HTTPS, confirmed by Abhi)
- **IP / SSH / instance details**: not yet confirmed for the GCP host -- the AWS Lightsail static-IP SSH details below are stale, do not use them. Update this section once the GCP instance details are known.
- **App dir**: `/home/ubuntu/whatsapp-dashboard` (unconfirmed on GCP -- verify actual path)
- **Service**: `whatsapp-dashboard` (systemd -- unconfirmed whether GCP host still uses systemd/nginx/gunicorn or a different setup, e.g. Cloud Run)

### Deploy an update
```bash
# On the server:
cd /home/ubuntu/whatsapp-dashboard && bash deploy/deploy.sh
```
This does: `git pull` → `pip install -r requirements.txt` → `sudo systemctl restart whatsapp-dashboard`

### Common server commands
```bash
sudo systemctl status whatsapp-dashboard
sudo systemctl restart whatsapp-dashboard
tail -f /home/ubuntu/whatsapp-dashboard/logs/app.log
journalctl -u whatsapp-dashboard -n 50
```

### Logs
- App log: `/home/ubuntu/whatsapp-dashboard/logs/app.log` (rotating, 5MB × 5 files)
- Access log: `/home/ubuntu/whatsapp-dashboard/logs/access.log`
- Systemd captures stderr → `app.log` via `StandardError=append:` in the service file

**Do NOT add a StreamHandler (console) in `setup_logging()`** — systemd already captures stderr to `app.log`, adding a console handler causes every log line to appear twice.

### Database backup
Daily cron job on the server backs up `whatsapp_dashboard.db`. Check with `crontab -l`.

---

## Auth / Users

- Registration is **closed** — `/signup` redirects to login with an error
- Only `hello@boxbox.in` should have access
- Users stored in `users.json` (gitignored)
- Login supports username or email

---

## WhatsApp Integration

- **API**: WhatsApp Cloud API (Meta)
- **Webhook URL**: `https://internal.boxbox.in/webhook` (updated in Meta Business Manager by Abhi after the GCP/domain migration)
- **Verify token**: `my_secret_webhook_token_2024` (in `.env` as `WEBHOOK_VERIFY_TOKEN`)
- **Rate limit**: 1200ms between messages (configurable via `RATE_LIMIT_*` env vars)
- **Queue status**: `GET /api/queue-status`

### Webhook events handled
- `delivered` → updates `delivered_at` on message, updates customer stats
- `read` → updates `read_at`, customer read count
- `failed` → marks message as `failed` in DB, adjusts campaign `success_count`/`failed_count`
- Incoming messages (replies) → updates `replied_at`, stores reply text

### Error 131049
Meta's "ecosystem health" throttle — message accepted by API (returns 200 + wamid) but later fails via webhook. The webhook `failed` handler now correctly marks these as `failed` in the DB and adjusts campaign counts. Use "Resend to Unsent" on the campaign details page to re-queue them.

---

## Campaign System

### Message flow
1. User submits send form → messages added to `MessageQueue` (in-memory)
2. Queue worker sends at rate-limited pace → marks each message `sent` in DB
3. WhatsApp webhooks update delivery/read/reply stats
4. Campaign status: `pending` → `running` → `completed`/`failed`

### Resend to Unsent
On the campaign details page, "Resend to Unsent (N)" button calls `POST /api/campaigns/<id>/resend-unsent`. This re-queues failed/queued messages within the **same campaign** (not a new one), using the stored `template_params`, `template_language`, and `button_params` from the original send.

### Scheduled campaigns
`background_scheduler.py` runs jobs in daemon threads. Scheduled time is in IST. Uses the same `MessageQueue` as immediate sends.

### If a campaign gets stuck at "running"
The in-memory queue was wiped by a service restart. Fix:
```bash
sqlite3 /home/ubuntu/whatsapp-dashboard/whatsapp_dashboard.db \
  "UPDATE campaigns SET status='failed' WHERE status='running';"
```
Then use "Resend to Unsent" on the campaign details page.

---

## Customer / Segment System

- Customers synced from Shopify via "Sync Shopify" button
- Phones stored as `+91XXXXXXXXXX` format
- WhatsApp webhooks send `recipient_id` without `+` prefix — `update_customer_message_stats()` normalises this automatically
- Segments: All, Has Phone, Engaged Last 7 Days, Not Engaged Last 7 Days, Never Messaged, High Value, Has Orders, Replied, + custom segments
- "Engaged Last 7 Days" = any of `last_message_sent`, `last_message_read`, or `last_message_replied` within 7 days
- "Not Engaged Last 7 Days" = `last_message_sent` is NULL or older than 7 days

---

## Design System

Dark + gold theme defined in `base.html`:
```css
--gold: #d4a84b
--gold-light: #e8c068
--bg: #0a0a0a
--surface: rgba(255,255,255,0.04)
--border: rgba(255,255,255,0.08)
--border-gold: rgba(212,168,75,0.3)
--text: #e2e8f0
--text-muted: rgba(255,255,255,0.5)
--text-dim: rgba(255,255,255,0.25)
```
Currency is ₹ (not $) throughout.

---

## Automation System (Shopify-triggered WhatsApp messages)

Settings page at `/automation`. Three event types, each with enable/disable toggle, template name, language, and delay.

### Shopify Webhook Endpoints

| Topic | URL | Handler |
|-------|-----|---------|
| `checkouts/create` | `/shopify/webhook/cart-create` | `shopify_cart_create()` |
| `orders/create` | `/shopify/webhook/order-create` | `shopify_order_create()` |
| `orders/fulfilled` OR `fulfillments/create` | `/shopify/webhook/fulfillment` | `shopify_fulfillment()` |
| `orders/cancelled` | `/shopify/webhook/order-cancelled` | `shopify_order_cancelled()` |
| `customers/create` | `/shopify/webhook/customer-created` | `shopify_customer_created()` |

Register all five in Shopify Admin → Settings → Notifications → Webhooks, pointed at `internal.boxbox.in`. The first three are used by the **Automation System** (described below); the last two are used by **Flows** triggers (`order_cancelled`, `customer_created`).

### Automation Event Types

**1. `order_confirmation`** — fires on `orders/create`
- Sends immediately when a new order is placed
- Template params: `{{1}}`=first name, `{{2}}`=order# (format: `#F1xxxx`), `{{3}}`=items with size/colour, `{{4}}`=total (₹)
- Tries to upload product image from Shopify as IMAGE header — falls back gracefully if unavailable
- To get product images: `SHOPIFY_ACCESS_TOKEN` needs `read_products` scope. Without it, no image header (template must have no IMAGE header)
- Approved WhatsApp template name in use: `order_created`

**2. `fulfillment`** — fires on `orders/fulfilled` or `fulfillments/create`
- Sends immediately when order is marked fulfilled in Shopify
- Template params: `{{1}}`=first name, `{{2}}`=order# (format: `#F1xxxx`), `{{3}}`=items with size/colour
- Tracking link goes as a **URL button** (NOT body text): button URL = `https://internal.boxbox.in/track/{{1}}` (dynamic, suffix = order number)
- The `/track/<order_ref>` public endpoint does a 302 redirect to the actual courier URL stored in DB
- Fallback chain for tracking: courier URL from Shopify → `order_status_url` (Shopify order page) → `boxbox.in`
- **CRITICAL**: Template button must be created as **Dynamic URL** type in WhatsApp Business Manager. If created as Static with literal `{{1}}`, WhatsApp appends the parameter instead of substituting it, causing URLs like `/track/{{1}}4525`
- Approved WhatsApp template name in use: `order_fulfilled` (UTILITY ✅)

**3. `abandoned_cart`** — background checker runs every 15 minutes
- Sends after configurable delay (default 1 hour) when a checkout is abandoned
- Template params: `{{1}}`=name/email prefix, `{{2}}`=items, `{{3}}`=total (₹)
- Discount code (BOXBOX5) is hardcoded in the template itself, not passed as a param

### Key Automation Helpers in app.py

```python
_format_items(line_items, max_items=3)
# → "Blue Sneakers (Size 9 / White) x2, Black Jeans (30 / Regular) & 1 more"
# Includes variant_title (size/colour). Skips "Default Title" placeholder.

_get_product_image_url(line_items)
# Tries line_items[].image.src first (often null in webhooks)
# Falls back to Shopify Admin API: GET /admin/api/2024-01/products/{product_id}.json
# Returns None if SHOPIFY_ACCESS_TOKEN lacks read_products scope (403)

_upload_image_from_url(image_url)
# Downloads image from URL, uploads to WhatsApp media API
# Returns media_id or None (non-fatal — send proceeds without header if None)

_get_webhook_user_id()
# Returns correct user_id for webhook processing
# Priority: automation_settings table → activity_log → users[0]
# CRITICAL: prevents bug where webhook uses wrong user_id and can't find settings

_normalize_phone_webhook(phone)
# Normalises any Indian phone format → E.164 (+91XXXXXXXXXX)

_verify_shopify_hmac(raw_data, hmac_header)
# Verifies Shopify webhook signature. Permissive (returns True) if SHOPIFY_WEBHOOK_SECRET not set.

_send_automation_message(phone, event_type, template_name, lang, params, header_media_id=None, button_params=None)
# Single wrapper for sending one automation template message

_start_abandoned_cart_checker()
# Daemon thread, sleeps 15min between runs, sends cart reminders
```

### Order Number Format
All automation messages use `#F1{order_number}` format (e.g. `#F14123`), not the raw Shopify `#4123`.

### Tracking Redirect Endpoint
`GET /track/<order_ref>` — **public, no login required**
- Looks up `tracking_url` from `shopify_orders` table by order number
- 302 redirects to courier URL (Delhivery, DTDC, etc.) if available
- Falls back to Shopify `order_status_url` if no courier URL
- Falls back to `https://boxbox.in` as last resort

### DB Tables Added for Automation

**`automation_settings`** — per-user, per-event configuration
```sql
user_id, event_type (UNIQUE), enabled, template_name, template_language, delay_hours, extra_data (JSON)
```

**`shopify_orders`** — stores Shopify orders for dedup + tracking
```sql
shopify_order_id (UNIQUE), order_number, customer_email, customer_phone,
total_price, financial_status, fulfillment_status, order_items (JSON),
confirmation_sent, confirmation_sent_at,
fulfillment_sent, fulfillment_sent_at,
tracking_url
```

**`abandoned_carts`** — tracks checkouts for cart reminder
```sql
shopify_cart_id (UNIQUE), customer_email, customer_phone,
cart_items (JSON), total_price, currency,
abandoned_at, cart_url, reminder_sent, reminder_sent_at, recovered
```

### upload_media_from_bytes (utils/whatsapp.py)
New function to upload raw image bytes (downloaded from Shopify CDN) to WhatsApp media API. Returns `media_id` or `None`. Used by `_upload_image_from_url` in app.py.

---

## Known Issues / Past Bugs Fixed

| Bug | Cause | Fix |
|-----|-------|-----|
| Queue processes nothing | `preload_app=True` kills threads at fork | Set `preload_app=False` |
| Campaign stops at ~200 messages | `max_requests=500` recycles worker, wipes queue | Set `max_requests=0` |
| Customer stats never update | Phone format mismatch: webhook sends `91XXX`, DB stores `+91XXX` | Normalise in `update_customer_message_stats` |
| 131049 errors shown as "sent" | Webhook `failed` handler only logged, didn't update DB | Call `fail_message_by_whatsapp_id` in failed handler |
| Double log lines | StreamHandler + systemd stderr capture both write to app.log | Removed StreamHandler |
| Engaged segment broken | SQLite `datetime()` returns space separator, stored timestamps use `T` | Use `strftime('%Y-%m-%dT%H:%M:%S','now','-7 days')` |
| Automation sends to wrong user | `users[0].id` ≠ logged-in user's id; webhook used wrong user_id to look up settings | `_get_webhook_user_id()` queries `automation_settings` table first |
| Order confirmation HTTP 400 | Template has IMAGE header but `line_items[].image` is null in Shopify webhook | Fetch product image via Shopify Admin API as fallback |
| Shopify product image API 403 | `SHOPIFY_ACCESS_TOKEN` lacks `read_products` scope | Either add scope, or create template without IMAGE header |
| Tracking button goes to boxbox.in | Template URL button created as Static with literal `{{1}}`; WhatsApp appends param instead of substituting | Recreate template button as **Dynamic URL** type in WhatsApp Business Manager |
| Tracking button goes to boxbox.in | No courier URL in Shopify webhook (only tracking number) | Fall back to `order_status_url` from Shopify payload |

---

## Local Development

```bash
# Install dependencies
python -m venv venv
venv\Scripts\activate   # Windows
pip install -r requirements.txt

# Create .env with required vars (see above)

# Run
python app.py
```

The app runs on `http://localhost:5000`. Webhooks won't work locally without ngrok.
