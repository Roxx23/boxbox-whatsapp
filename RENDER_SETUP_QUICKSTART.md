# Quick Setup Guide for Render.com Deployment

## Step 1: Prepare Your Code

Your code is now ready for deployment with persistent storage support!

### What was configured:
✅ Database path supports environment variable `DATABASE_PATH`
✅ Log file path supports environment variable `LOG_FILE_PATH`  
✅ Users file path supports environment variable `USERS_FILE_PATH`
✅ Procfile and runtime.txt created
✅ gunicorn added to requirements

---

## Step 2: Push to GitHub

```bash
# If not already a git repo
git init

# Add all files
git add .

# Commit
git commit -m "Ready for Render deployment with persistent storage"

# Create repo on GitHub and push
git remote add origin https://github.com/YOUR_USERNAME/whatsapp-dashboard.git
git branch -M main
git push -u origin main
```

---

## Step 3: Deploy to Render.com

### 3.1 Create Web Service

1. Go to https://render.com and sign up
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository
4. Configure:
   - **Name**: `whatsapp-dashboard`
   - **Region**: Select closest to you
   - **Branch**: `main`
   - **Root Directory**: (leave empty)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements_new.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`

### 3.2 Add Environment Variables

In the "Environment" section, add:

```
WHATSAPP_ACCESS_TOKEN=your_actual_token
WHATSAPP_PHONE_NUMBER_ID=your_actual_phone_id
WABA_ID=your_actual_waba_id
SECRET_KEY=your_very_long_random_secret_key_123456
SHOPIFY_SHOP_NAME=your-store-name
SHOPIFY_ACCESS_TOKEN=your_shopify_token
```

### 3.3 Click "Create Web Service"

Wait for deployment (takes 2-5 minutes). You'll get a URL like:
`https://whatsapp-dashboard-xxxx.onrender.com`

---

## Step 4: Add Persistent Storage

### 4.1 Add Disk

1. In your Render service dashboard, click **"Disks"** (left sidebar)
2. Click **"Add Disk"**
3. Configure:
   - **Name**: `whatsapp-data`
   - **Mount Path**: `/data`
   - **Size**: 1 GB (free)
4. Click **"Save"**

### 4.2 Add Storage Environment Variables

Go back to "Environment" tab and add:

```
DATABASE_PATH=/data/whatsapp_dashboard.db
LOG_FILE_PATH=/data/logs.csv
USERS_FILE_PATH=/data/users.json
```

### 4.3 Redeploy

Click **"Manual Deploy"** → **"Deploy latest commit"**

Your data will now persist across deployments! 🎉

---

## Step 5: Configure Webhooks

### 5.1 Meta WhatsApp Webhook

1. Copy your Render URL: `https://your-app.onrender.com`
2. Go to Meta Developer Console → Your App → WhatsApp → Configuration
3. Set webhook URL: `https://your-app.onrender.com/webhook`
4. Set verify token: (same as your WEBHOOK_VERIFY_TOKEN)
5. Subscribe to: `messages`, `message_reactions`

### 5.2 Shopify Webhooks

1. Go to Shopify Admin → Settings → Notifications → Webhooks
2. Create webhooks:
   - **Cart creation**: `https://your-app.onrender.com/shopify/webhook/cart`
   - **Order creation**: `https://your-app.onrender.com/shopify/webhook/order`
   - **Format**: JSON

---

## Step 6: Keep App Awake (Important!)

Free tier sleeps after 15 minutes → webhooks will be missed!

### Use UptimeRobot (Free)

1. Go to https://uptimerobot.com and sign up
2. Add Monitor:
   - **Monitor Type**: HTTP(s)
   - **Friendly Name**: WhatsApp Dashboard
   - **URL**: `https://your-app.onrender.com`
   - **Monitoring Interval**: Every 14 minutes
3. Click **"Create Monitor"**

Your app will now stay awake 24/7! ✅

---

## Step 7: Create Admin User

After deployment, visit your app and create the first admin user:

`https://your-app.onrender.com/register`

---

## Step 8: Share with Team

Your team can access the dashboard at:
`https://your-app.onrender.com`

Each member needs their own login (create from admin panel).

---

## Troubleshooting

### Check Logs
1. In Render dashboard, click **"Logs"** tab
2. Look for errors during startup

### Common Issues

**App won't start:**
- Check all environment variables are set
- Verify SECRET_KEY is at least 16 characters
- Check Render logs for specific error

**Database not persisting:**
- Verify disk is mounted at `/data`
- Check environment variables point to `/data/...`

**Webhooks not working:**
- Verify app is awake (use UptimeRobot)
- Check webhook URLs in Meta/Shopify
- Test webhook with curl:
  ```bash
  curl https://your-app.onrender.com/webhook
  ```

**App sleeping:**
- Add UptimeRobot monitor (14-minute interval)
- Or upgrade to Render paid plan ($7/month for always-on)

---

## Monitoring

### View Logs
```bash
# In Render dashboard → Logs tab
# Or use Render CLI
render logs -f
```

### Database Backup
Regularly backup your database:
1. Render dashboard → Shell tab
2. Run: `sqlite3 /data/whatsapp_dashboard.db .dump > backup.sql`
3. Download backup

---

## Cost Summary

- **Render Web Service**: Free (with sleep)
- **Persistent Disk**: Free (1GB)
- **UptimeRobot**: Free (50 monitors)
- **Total**: $0/month

For production with no sleep: Render Starter ($7/month)

---

## Next Steps

✅ Your app is deployed
✅ Data persists across deployments
✅ Webhooks configured
✅ App stays awake 24/7
✅ Team can access via URL

Share the URL with your team and start using WhatsApp Dashboard! 🚀
