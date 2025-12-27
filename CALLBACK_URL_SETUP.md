# Webhook Callback URL Setup Guide

## What You Need

When ngrok is running, it gives you a URL like this:
```
Forwarding: https://abc123.ngrok.io -> http://localhost:5000
```

## Step-by-Step Setup

### Step 1: Start Your Flask App

```bash
# Terminal 1
python app.py
```

You should see:
```
* Running on http://127.0.0.1:5000
```

### Step 2: Start Ngrok

```bash
# Terminal 2
ngrok http 5000
```

You'll see something like:
```
Session Status                online
Account                       YourName (Plan: Free)
Version                       3.x.x
Region                        United States (us)
Forwarding                    https://1a2b-3c4d-5e6f.ngrok-free.app -> http://localhost:5000

Connections                   ttl     opn     rt1     rt5     p50     p90
                              0       0       0.00    0.00    0.00    0.00
```

### Step 3: Copy the HTTPS URL

**Look for the line that says "Forwarding":**
```
Forwarding: https://1a2b-3c4d-5e6f.ngrok-free.app -> http://localhost:5000
```

**Copy this part:**
```
https://1a2b-3c4d-5e6f.ngrok-free.app
```

⚠️ **Important:**
- ✅ Copy the HTTPS URL (not http)
- ✅ Don't include the " -> http://localhost:5000" part
- ✅ Your URL will be different each time ngrok restarts

### Step 4: Create Your Callback URL

Add `/webhook` to the end:

```
https://1a2b-3c4d-5e6f.ngrok-free.app/webhook
```

**This is your Callback URL!**

---

## Configure in Meta Developer Console

### Step 1: Go to Meta Developer Console

1. Visit: https://developers.facebook.com/
2. Click on your app
3. In the left sidebar, click **WhatsApp** → **Configuration**

### Step 2: Add Webhook

1. Find the **Webhook** section
2. Click **Edit** or **Configure Webhook**

### Step 3: Enter Details

**Callback URL:**
```
https://1a2b-3c4d-5e6f.ngrok-free.app/webhook
```

**Verify Token:**
```
my_secret_webhook_token_2024
```
(Use whatever you put in your .env file)

### Step 4: Subscribe to Fields

Check these boxes:
- ✅ **messages** (for replies)
- ✅ **message_status** (for delivered/read status)

### Step 5: Verify and Save

1. Click **Verify and Save**
2. WhatsApp will test your webhook
3. You should see "✅ Webhook verified" in your Flask console

---

## Complete Example

### Your Setup:

**Terminal 1 (Flask):**
```bash
C:\Users\AbHiShEk\boxbox\whatsapp-dashboard> python app.py

 * Running on http://127.0.0.1:5000
```

**Terminal 2 (Ngrok):**
```bash
C:\Users\AbHiShEk\boxbox\whatsapp-dashboard> ngrok http 5000

Forwarding: https://abc123xyz.ngrok-free.app -> http://localhost:5000
```

**Your .env file:**
```env
WEBHOOK_VERIFY_TOKEN=my_secret_webhook_token_2024
```

**Meta Console Configuration:**
```
Callback URL: https://abc123xyz.ngrok-free.app/webhook
Verify Token: my_secret_webhook_token_2024
```

---

## Test Your Webhook

### Test 1: Browser Test

Open in your browser:
```
https://your-ngrok-url.ngrok-free.app/webhook?hub.mode=subscribe&hub.verify_token=my_secret_webhook_token_2024&hub.challenge=hello
```

**Expected:** Browser shows `hello`

### Test 2: Check Flask Console

After configuring in Meta Console, you should see:
```
✅ Webhook verified
```

### Test 3: Send a Message

1. Send a WhatsApp message from your dashboard
2. Check Flask console for:
```
📥 Webhook received: {...}
📊 Status update: wamid.xxx -> delivered
👁️ Status update: wamid.xxx -> read
```

---

## Important Notes

### ⚠️ Ngrok URLs Change!

Every time you restart ngrok, you get a **NEW URL**:
```
# First time
https://abc123.ngrok-free.app

# After restart (DIFFERENT!)
https://xyz789.ngrok-free.app
```

**What to do:**
1. Get new URL from ngrok
2. Update in Meta Console
3. Click "Verify and Save" again

### 💡 Keep Ngrok Running

While testing:
- Keep Flask running in Terminal 1
- Keep ngrok running in Terminal 2
- Don't close either terminal!

### 🔒 Use HTTPS, Not HTTP

**Wrong:**
```
❌ http://abc123.ngrok-free.app/webhook
```

**Correct:**
```
✅ https://abc123.ngrok-free.app/webhook
```

---

## Troubleshooting

### Problem: "Webhook verification failed"

**Check 1: Verify Token**
Make sure the token in Meta Console matches your .env file exactly:

```env
# .env file
WEBHOOK_VERIFY_TOKEN=my_secret_token

# Meta Console
Verify Token: my_secret_token  ← Must be EXACTLY the same!
```

**Check 2: Flask Running**
Make sure Flask app is running:
```bash
python app.py
# Should show: * Running on http://127.0.0.1:5000
```

**Check 3: Ngrok Running**
Make sure ngrok is running:
```bash
ngrok http 5000
# Should show: Forwarding: https://...
```

**Check 4: URL Correct**
Make sure URL includes `/webhook`:
```
✅ https://abc123.ngrok-free.app/webhook
❌ https://abc123.ngrok-free.app
```

### Problem: "Cannot reach webhook URL"

**Solution:**
1. Make sure ngrok is running
2. Copy the HTTPS URL (not http)
3. Add `/webhook` to the end
4. Update in Meta Console

### Problem: Webhook verified but no events

**Check Subscriptions:**
1. In Meta Console
2. WhatsApp → Configuration
3. Webhook section
4. Make sure checked:
   - ✅ messages
   - ✅ message_status

---

## Quick Reference

### What You Need:

1. **Flask app running:** `python app.py`
2. **Ngrok running:** `ngrok http 5000`
3. **Ngrok URL:** Copy from "Forwarding" line
4. **Add /webhook:** `https://your-url.ngrok-free.app/webhook`
5. **Verify Token:** From your .env file

### Full URLs:

```
Ngrok URL:     https://abc123.ngrok-free.app
Callback URL:  https://abc123.ngrok-free.app/webhook  ← Use this in Meta Console
Test URL:      https://abc123.ngrok-free.app/webhook?hub.mode=subscribe&hub.verify_token=YOUR_TOKEN&hub.challenge=test
```

---

## For Production (Later)

When you deploy to a real server:

**Example with domain:**
```
Callback URL: https://yourdomain.com/webhook
```

**Example with Heroku:**
```
Callback URL: https://your-app-name.herokuapp.com/webhook
```

**Example with DigitalOcean:**
```
Callback URL: https://your-ip-address/webhook
```

For now, just use ngrok for testing! 🚀

---

## Summary Checklist

Setup complete when:
- ☐ Flask app running (Terminal 1)
- ☐ Ngrok running (Terminal 2)
- ☐ Copied ngrok HTTPS URL
- ☐ Added /webhook to URL
- ☐ Configured in Meta Console
- ☐ Used same verify token
- ☐ Subscribed to messages & message_status
- ☐ Clicked "Verify and Save"
- ☐ Saw "✅ Webhook verified" in Flask console
- ☐ Browser test shows "hello"
- ☐ Ready to track engagement! 🎉
