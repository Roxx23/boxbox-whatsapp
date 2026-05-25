# WhatsApp Dashboard — Project Context

## What This Is

A Flask web app for sending WhatsApp marketing campaigns to Shopify customers.
Owner: Abhi (hello@boxbox.in) — single-user, registration is closed.

Live URL: https://dashboard.boxbox.in

---

## Tech Stack

- **Backend**: Python 3 / Flask
- **Database**: SQLite (`whatsapp_dashboard.db`) — kept intentionally over PostgreSQL (single server, 1 gunicorn worker, no concurrent write issues)
- **Queue**: In-memory `MessageQueue` (utils/rate_limiter.py) — messages are lost on restart
- **Auth**: Flask-Login + bcrypt, users stored in `users.json`
- **Server**: AWS Lightsail $5/month, Ubuntu 22.04, Mumbai region
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
SHOPIFY_SHOP_NAME=...
SHOPIFY_ACCESS_TOKEN=...
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
- **Provider**: AWS Lightsail
- **IP**: has a static IP (check Lightsail console)
- **Domain**: `dashboard.boxbox.in` (subdomain of boxbox.in, DNS A record points to static IP)
- **SSH**: `ssh ubuntu@<static-ip>` with `.pem` key
- **App dir**: `/home/ubuntu/whatsapp-dashboard`
- **Service**: `whatsapp-dashboard` (systemd)

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
- **Webhook URL**: `https://dashboard.boxbox.in/webhook`
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

## Known Issues / Past Bugs Fixed

| Bug | Cause | Fix |
|-----|-------|-----|
| Queue processes nothing | `preload_app=True` kills threads at fork | Set `preload_app=False` |
| Campaign stops at ~200 messages | `max_requests=500` recycles worker, wipes queue | Set `max_requests=0` |
| Customer stats never update | Phone format mismatch: webhook sends `91XXX`, DB stores `+91XXX` | Normalise in `update_customer_message_stats` |
| 131049 errors shown as "sent" | Webhook `failed` handler only logged, didn't update DB | Call `fail_message_by_whatsapp_id` in failed handler |
| Double log lines | StreamHandler + systemd stderr capture both write to app.log | Removed StreamHandler |
| Engaged segment broken | SQLite `datetime()` returns space separator, stored timestamps use `T` | Use `strftime('%Y-%m-%dT%H:%M:%S','now','-7 days')` |

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
