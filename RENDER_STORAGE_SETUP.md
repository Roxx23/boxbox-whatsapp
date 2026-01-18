# Render.com Persistent Storage Setup

## Why You Need This
By default, Render's free tier resets your SQLite database on every deploy. This means you'll lose:
- User accounts
- Message logs
- Campaign history
- Shopify sync data
- Scheduled messages

## Solution: Add Persistent Disk

### Steps:
1. After creating your web service on Render
2. Go to your service dashboard
3. Click **"Disks"** in left sidebar
4. Click **"Add Disk"**
5. Configure:
   - **Name**: `whatsapp-data`
   - **Mount Path**: `/data`
   - **Size**: 1 GB (free tier includes 1GB)
6. Click **"Save"**

### Update Database Path

Edit your `app.py` or database initialization to use `/data` directory:

```python
# Before (development)
DB_PATH = 'whatsapp_dashboard.db'

# After (production with persistent disk)
import os
DB_PATH = os.getenv('DATABASE_PATH', 'whatsapp_dashboard.db')

# In Render, set environment variable:
# DATABASE_PATH=/data/whatsapp_dashboard.db
```

## Alternative: Use PostgreSQL (Recommended for Production)

Render provides free PostgreSQL database:

### Steps:
1. In Render dashboard, click **"New +"** → **"PostgreSQL"**
2. Name it `whatsapp-db`
3. Select **Free** tier (90 days, then $7/month)
4. Copy the **Internal Database URL**
5. In your web service, add environment variable:
   - `DATABASE_URL`: (paste the internal URL)

### Migrate from SQLite to PostgreSQL:

```bash
# Install SQLAlchemy
pip install sqlalchemy psycopg2-binary

# Update requirements_new.txt
echo "sqlalchemy==2.0.23" >> requirements_new.txt
echo "psycopg2-binary==2.9.9" >> requirements_new.txt
```

## Shopify Webhook Configuration

After deployment with persistent storage:

1. **Get your Render URL**: `https://your-app.onrender.com`

2. **Configure Shopify webhooks**:
   - Go to Shopify Admin → Settings → Notifications → Webhooks
   - Add webhooks:
     - **Cart created**: `https://your-app.onrender.com/shopify/webhook/cart`
     - **Order created**: `https://your-app.onrender.com/shopify/webhook/order`
     - **Format**: JSON

3. **Set webhook verification**:
   - Shopify signs webhooks with HMAC
   - Make sure `SHOPIFY_ACCESS_TOKEN` is set in environment variables

## Testing

After setup:
1. Create a test abandoned cart in Shopify
2. Check Render logs to see webhook received
3. Verify data persists after app restart
4. Test scheduled messages continue after sleep/wake

## Backup Strategy

Even with persistent disk, backup regularly:
```bash
# Export database (run locally with Render DB mounted)
sqlite3 /data/whatsapp_dashboard.db .dump > backup.sql

# Or use Render shell access to download
```

## Important Notes

- **Free persistent disk**: 1 GB limit, enough for most use cases
- **Database writes**: SQLite on disk is slower than in-memory
- **For heavy traffic**: Consider PostgreSQL instead
- **Backups**: Render doesn't auto-backup free tier databases
