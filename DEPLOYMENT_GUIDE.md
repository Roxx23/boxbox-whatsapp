# Deployment Guide for WhatsApp Dashboard

## Free Hosting Options

### Option 1: Render.com (Recommended)

**Steps:**
1. Push your code to GitHub
2. Go to https://render.com and sign up
3. Click "New +" → "Web Service"
4. Connect your GitHub repository
5. Configure:
   - **Name**: whatsapp-dashboard
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements_new.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`
6. Add Environment Variables:
   - `WHATSAPP_ACCESS_TOKEN`
   - `WHATSAPP_PHONE_NUMBER_ID`
   - `WABA_ID`
   - `SECRET_KEY`
   - `SHOPIFY_SHOP_NAME` (if using Shopify)
   - `SHOPIFY_ACCESS_TOKEN` (if using Shopify)
7. Click "Create Web Service"

**Note**: Free tier sleeps after 15 min inactivity. Use a service like UptimeRobot to ping it every 14 minutes.

---

### Option 2: Railway.app

**Steps:**
1. Push code to GitHub
2. Go to https://railway.app and sign up
3. Click "New Project" → "Deploy from GitHub repo"
4. Select your repository
5. Add environment variables (same as above)
6. Deploy automatically starts

**Benefits**: $5 free credit/month, no sleep mode

---

### Option 3: PythonAnywhere

**Steps:**
1. Sign up at https://www.pythonanywhere.com
2. Upload your project files
3. Create a virtual environment:
   ```bash
   mkvirtualenv --python=/usr/bin/python3.9 myenv
   pip install -r requirements_new.txt
   ```
4. Configure Web app:
   - Framework: Flask
   - Python version: 3.9
   - Source code: /home/yourusername/whatsapp-dashboard
   - Working directory: /home/yourusername/whatsapp-dashboard
5. Set environment variables in WSGI file
6. Reload web app

---

## Database Considerations

Your SQLite database (`whatsapp_dashboard.db`) will work fine on all platforms. However:
- **Render/Railway**: Database resets on each deploy (use persistent storage or PostgreSQL)
- **PythonAnywhere**: Files persist

For production, consider migrating to PostgreSQL (free tier available on all platforms).

---

## Webhook Configuration

After deployment, update WhatsApp webhook URL:
1. Get your deployment URL (e.g., `https://your-app.onrender.com`)
2. Update webhook in Meta Developer Console:
   - URL: `https://your-app.onrender.com/webhook`
   - Verify token: (your verification token)
3. Subscribe to webhook events: messages, message_reactions

---

## Security Checklist

✅ Set strong `SECRET_KEY` in environment variables
✅ Never commit `.env` file to GitHub
✅ Use HTTPS (automatic on all platforms)
✅ Keep access tokens secure
✅ Regularly rotate API keys

---

## GitHub Setup (If Not Already Done)

```bash
# Initialize git repository
git init

# Create .gitignore
echo "venv/" >> .gitignore
echo "__pycache__/" >> .gitignore
echo "*.db" >> .gitignore
echo ".env" >> .gitignore
echo "logs.csv" >> .gitignore

# Add and commit
git add .
git commit -m "Initial commit"

# Create GitHub repository and push
git remote add origin https://github.com/yourusername/whatsapp-dashboard.git
git branch -M main
git push -u origin main
```

---

## Team Access

After deployment, share the URL with your team:
- Each team member needs login credentials (configured in `users.json`)
- Admin can create/manage users through the dashboard

---

## Troubleshooting

**Issue**: App crashes on startup
- Check environment variables are set correctly
- Check logs in hosting platform dashboard

**Issue**: Database not persisting
- Use persistent volume (Render/Railway) or switch to PostgreSQL

**Issue**: Webhook not receiving messages
- Verify webhook URL in Meta Developer Console
- Check SSL certificate is valid
- Test with webhook test tool

---

## Keep Render Free Tier Awake

Use UptimeRobot (free):
1. Sign up at https://uptimerobot.com
2. Add new monitor:
   - Type: HTTP(s)
   - URL: Your Render URL
   - Interval: 14 minutes
3. This prevents your app from sleeping
