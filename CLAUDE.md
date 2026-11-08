# WhatsApp Dashboard — Project Context

## What This Is

A Flask web app for sending WhatsApp marketing campaigns to Shopify customers.
Owner: Abhi (hello@boxbox.in) — single-user, registration is closed.

Live URL: https://internal.boxbox.in (migrated from dashboard.boxbox.in -- see Deployment section)

---

## Tech Stack

- **Backend**: Python 3 / Flask
- **Database**: SQLite (`whatsapp_dashboard.db`) — kept intentionally over PostgreSQL (single server, 1 gunicorn worker, no concurrent write issues)
- **Queue**: In-memory `MessageQueue` (utils/rate_limiter.py). Unsent campaign messages are re-queued from the DB on startup (see Campaign System → Restart resume)
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
SHOPIFY_CLIENT_ID=...          # Dev Dashboard app (preferred). With CLIENT_ID + CLIENT_SECRET set, the app gets its
SHOPIFY_CLIENT_SECRET=...      #   own Admin API token via the client-credentials grant; it expires every 24h and is
                               #   renewed automatically (utils/shopify_auth.py). Scopes: read_customers, read_orders,
                               #   read_products, write_price_rules, write_discounts
SHOPIFY_ACCESS_TOKEN=...       # optional static token; used only when CLIENT_ID/SECRET are not set, or as a
                               #   last resort if the grant fails. The old custom app token gets 403
                               #   "API Access has been disabled" since about 2026-10-25
SHOPIFY_WEBHOOK_SECRET=...     # optional — if set, verifies Shopify webhook HMAC signatures
```

Location on server: `/home/ubuntu/whatsapp-dashboard/.env`

Shopify Admin API version: `2025-10` (`API_VERSION` in `utils/shopify_auth.py`). Every Admin API call goes
through `shopify_request()` there: it adds the current token and, on a 401, renews the token once and retries.
Never log the token or the client secret.

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
- **Provider**: GCP VM (migrated from AWS Lightsail as of 2026-09-14)
- **Domain**: `internal.boxbox.in` (subdomain of boxbox.in, replaces `dashboard.boxbox.in` -- publicly reachable HTTPS)
- **SSH**: user `sayboxbox` (verified 2026-09-18)
- **App dir**: `/home/sayboxbox/boxbox-whatsapp` (verified 2026-09-18)
- **Service**: `whatsapp-dashboard` (systemd, service name unconfirmed — see "Finding your service name" below)
- **Logs**: `/home/sayboxbox/boxbox-whatsapp/logs/app.log`

### Auto-deploy: GitHub Actions

Every push to `main` (including merged PRs) automatically deploys to production via GitHub Actions.

The workflow:
1. GitHub detects a push to `main`
2. Runs `.github/workflows/deploy.yml`
3. SSHes into the GCP server as `sayboxbox`
4. Runs `deploy/deploy.sh` which:
   - Pulls latest code from GitHub
   - Installs dependencies
   - Restarts the systemd service
   - Verifies the service is active
   - Health-checks localhost:5000 if accessible

**To enable auto-deploy**, Abhi must complete the one-time setup (see "ONE-TIME SETUP" section below in the PR description when this is merged).

### Deploy manually (if needed)
```bash
# On the GCP server, SSH as sayboxbox:
cd /home/sayboxbox/boxbox-whatsapp && bash deploy/deploy.sh
```

### Finding your service name
On the GCP server:
```bash
# List all active services containing "whatsapp" or "boxbox"
sudo systemctl list-units --type=service | grep -E 'whatsapp|boxbox'

# Or check what the current systemd service is running:
ps aux | grep gunicorn
sudo systemctl cat whatsapp-dashboard  # if the name is known
```

### Common server commands
```bash
sudo systemctl status whatsapp-dashboard
sudo systemctl restart whatsapp-dashboard
tail -f /home/sayboxbox/boxbox-whatsapp/logs/app.log
journalctl -u whatsapp-dashboard -n 50
```

### Logs
- App log: `/home/sayboxbox/boxbox-whatsapp/logs/app.log` (rotating, 5MB × 5 files)
- Access log: `/home/sayboxbox/boxbox-whatsapp/logs/access.log`
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
- **Send rate**: `RATE_LIMIT_REQUESTS` per `RATE_LIMIT_WINDOW` seconds (default 8/1.0s) across `MESSAGE_QUEUE_WORKERS` sender threads (default 4). One thread manages only ~2 sends/s (each is an HTTPS round trip), so the cap needs several threads. These are threads inside the single gunicorn worker; gunicorn `workers` stays 1. Meta allows 80 msg/s per number. Prod `.env` overrides these (check it before assuming the defaults).
- **Graph connections**: every Graph call in `utils/whatsapp.py` goes through `_http()`, a `requests.Session` per thread (`threading.local`) that keeps its connection open and is rebuilt after 50s idle. Do not call `requests.post/get` directly for Graph: on the 2-vCPU prod VM a new TLS (encrypted connection) handshake costs ~1.5s and ~0.5s of CPU, which held prod to ~1.4 msg/s (2026-11-07). Timeouts are `(CONNECT_TIMEOUT=5, read)`. Only connect errors are retried, never reads, so a POST can't double-send. Webhook payloads log at DEBUG.
- **Queue status**: `GET /queue-status` (in-memory queue, since app start). `GET /api/campaigns/progress`: per-campaign sent/failed/queued, rate and ETA from the DB. Used by the dashboard's "In progress" panel.
- **Template definitions** used by `send_template` (button layout) are cached in memory for 10 min (`_get_template_definition` in utils/whatsapp.py). Never call `get_templates()` per send: it pages through Meta's whole template list, and that made campaigns crawl at ~0.5 msg/s.

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
1. User submits send form → a `queued` row per message in DB + added to `MessageQueue` (in-memory)
2. A sender thread claims the row (`queued` → `sending`, one atomic UPDATE; it skips the row if the claim fails, so nothing is double-sent), sends at the rate-limited pace, then marks it `sent`/`failed`. It retries only 429 and HTTP 5xx (backoff 2/4/8s). Other 4xx are permanent. A timeout isn't retried because it may have been delivered.
3. WhatsApp webhooks update delivery/read/reply stats
4. Campaign status: `pending` → `running` → `completed`/`failed`

### Resend to Unsent
On the campaign details page, "Resend to Unsent (N)" button calls `POST /api/campaigns/<id>/resend-unsent`. This re-queues failed/queued messages within the **same campaign** (not a new one), using the stored `template_params`, `template_language`, and `button_params` from the original send.

### Scheduled campaigns
`background_scheduler.py` runs jobs in daemon threads. Scheduled time is in IST. Uses the same `MessageQueue` as immediate sends.

### Restart resume
A restart (including every auto-deploy) wipes the in-memory queue. On startup `_resume_interrupted_campaigns()` (app.py):
- re-queues `queued` rows with no `whatsapp_message_id` for campaigns still `pending`/`running`, created within the last 24h (`QUEUE_RESUME_MAX_AGE_HOURS`), so a campaign never goes out days late;
- marks rows left in `sending` (mid-API-call at shutdown) as `failed` with an "Interrupted by an app restart" error. They are never auto-resent, because they may have been delivered.
Disable with `QUEUE_RESUME_ON_START=0`.

### If a campaign gets stuck at "running"
Normally the restart resume above picks it up. For rows older than 24h, or to stop a campaign for good:
```bash
sqlite3 /home/sayboxbox/boxbox-whatsapp/whatsapp_dashboard.db   "UPDATE campaigns SET status='failed' WHERE status='running';"
```
Then use "Resend to Unsent" on the campaign details page if you still want it sent.

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
| `refunds/create` | `/shopify/webhook/order-refunded` | `shopify_order_refunded()` |
| `customers/create` | `/shopify/webhook/customer-created` | `shopify_customer_created()` |

Register all six in Shopify Admin → Settings → Notifications → Webhooks, pointed at `internal.boxbox.in`. The first three are used by the **Automation System** (described below); the last three are used by **Flows** triggers (`order_cancelled`, `order_refunded`, `customer_created`).

### Automation Event Types

**1. `order_confirmation`** — fires on `orders/create`
- Sends immediately when a new order is placed
- Template params: `{{1}}`=first name, `{{2}}`=order# (format: `#F1xxxx`), `{{3}}`=items with size/colour, `{{4}}`=total (₹)
- Tries to upload product image from Shopify as IMAGE header — falls back gracefully if unavailable
- **Flows (the live path)**: a send_message node with an IMAGE-header template and header source "Auto — product image from order" sends the ordered variant's photo (Shopify Admin API, first 2 line items, 5s each; compressed if over 5MB). If no photo is found it sends the node's fallback image ("If the order has no product photo, send": an image URL or an uploaded image). With no fallback the step is recorded `skipped`, because WhatsApp rejects an image-header template sent without one (400). Template `order_created_image` (= `order_created` + IMAGE header) was submitted 2026-11-08 for this.
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
