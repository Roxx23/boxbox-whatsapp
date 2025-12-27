# Simple Webhook Setup Guide

## What is a Verify Token?

A verify token is just a **secret password** that you create. It's used to make sure that WhatsApp is really the one sending data to your app (not a hacker).

Think of it like a secret handshake between your app and WhatsApp! 🤝

---

## Step 1: Create Your Verify Token

The verify token can be **ANY random string you want**. Just make it hard to guess!

### Easy Methods:

**Method 1: Random String (Simplest)**
Just type some random characters:
```
my_secret_webhook_token_2024
```

**Method 2: Use Online Generator**
Go to: https://www.random.org/strings/
- Set length to 32
- Click "Get Strings"
- Copy the result

**Method 3: Use Python (if you have it)**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Method 4: Simple Random Text**
Smash your keyboard randomly:
```
asd89f7h2jkl3mn4qwer5tyui6op
```

### Example Tokens:
```
whatsapp_verify_2024_secret
my-super-secret-webhook-token
abc123xyz789webhook2024
Tr7$mK9#pL2@nQ5!
```

**ANY of these work! Just pick one and remember it!**

---

## Step 2: Add Token to Your .env File

1. **Open your `.env` file** (in the project root folder)

2. **Add this line:**
   ```env
   WEBHOOK_VERIFY_TOKEN=your_token_here
   ```

3. **Replace `your_token_here` with your token:**
   ```env
   WEBHOOK_VERIFY_TOKEN=my_secret_webhook_token_2024
   ```

4. **Save the file**

### Complete Example .env File:
```env
# WhatsApp API Credentials
WHATSAPP_ACCESS_TOKEN=your_whatsapp_access_token
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id
WABA_ID=your_waba_id

# App Settings
SECRET_KEY=your_flask_secret_key

# NEW: Webhook Token (add this)
WEBHOOK_VERIFY_TOKEN=my_secret_webhook_token_2024
```

---

## Step 3: Configure Webhook in Meta Developer Console

Now you need to tell WhatsApp about your webhook.

### 3.1 Get Your Webhook URL

**If running locally (testing):**

1. Install ngrok:
   ```bash
   # Download from: https://ngrok.com/download
   ```

2. Start your Flask app:
   ```bash
   python app.py
   ```

3. In another terminal, start ngrok:
   ```bash
   ngrok http 5000
   ```

4. Copy the HTTPS URL:
   ```
   https://abc123.ngrok.io  ← Copy this!
   ```

5. Your webhook URL is:
   ```
   https://abc123.ngrok.io/webhook
   ```

**If running on server (production):**
```
https://yourdomain.com/webhook
```

### 3.2 Configure in Meta Console

1. **Go to:** https://developers.facebook.com/

2. **Click on your app**

3. **Go to:** WhatsApp → Configuration

4. **Find "Webhook" section**

5. **Click "Edit"**

6. **Enter your webhook details:**
   ```
   Callback URL: https://abc123.ngrok.io/webhook
   Verify Token: my_secret_webhook_token_2024
   ```
   ⚠️ **Use the SAME token from your .env file!**

7. **Click "Verify and Save"**

8. **Subscribe to fields:**
   - ✅ messages
   - ✅ message_status

9. **Click "Save"**

---

## Step 4: Test It Works

### Test 1: Check Webhook Endpoint

Open in browser:
```
http://localhost:5000/webhook?hub.mode=subscribe&hub.verify_token=my_secret_webhook_token_2024&hub.challenge=test123
```

**Expected result:** Should show `test123`

### Test 2: Send a Test Message

1. Send a WhatsApp message to someone
2. Check your console logs
3. Look for:
   ```
   📥 Webhook received: {...}
   📊 Status update: message_id -> delivered
   ```

### Test 3: Check Analytics

1. Go to Analytics page
2. Look for engagement metrics:
   - Delivered count
   - Read count
   - Replied count

---

## Common Issues & Solutions

### ❌ Problem: "Webhook verification failed"

**Cause:** Verify token doesn't match

**Solution:**
1. Check your .env file token
2. Check the token you entered in Meta Console
3. Make sure they are EXACTLY the same (case-sensitive!)
4. Restart your Flask app after changing .env

### ❌ Problem: "Webhook not receiving events"

**Cause:** URL not accessible

**Solution:**
1. Make sure ngrok is running
2. Make sure Flask app is running
3. Check the URL in Meta Console matches ngrok URL
4. Restart ngrok if URL changed

### ❌ Problem: "Cannot access localhost"

**Cause:** Meta can't reach localhost directly

**Solution:**
- ✅ MUST use ngrok for local testing
- ❌ CANNOT use http://localhost:5000

### ❌ Problem: "Engagement metrics not updating"

**Cause:** Webhook not configured properly

**Solution:**
1. Verify webhook setup (Steps above)
2. Check console logs for webhook events
3. Test the endpoint with curl
4. Make sure subscribed to `message_status`

---

## Quick Reference Card

```
┌─────────────────────────────────────────┐
│  WEBHOOK SETUP CHECKLIST                │
├─────────────────────────────────────────┤
│ ☐ Create verify token (any random text)│
│ ☐ Add to .env file                      │
│ ☐ Start Flask app (python app.py)      │
│ ☐ Start ngrok (ngrok http 5000)        │
│ ☐ Copy ngrok HTTPS URL                 │
│ ☐ Add /webhook to URL                  │
│ ☐ Configure in Meta Console             │
│ ☐ Use SAME verify token                │
│ ☐ Subscribe to messages & status       │
│ ☐ Test with browser                    │
│ ☐ Send test message                    │
│ ☐ Check analytics                      │
└─────────────────────────────────────────┘
```

---

## Visual Flow

```
┌──────────────────┐
│ 1. Create Token  │ ← Just type random text
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 2. Add to .env   │ ← WEBHOOK_VERIFY_TOKEN=your_token
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 3. Start App     │ ← python app.py
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 4. Start Ngrok   │ ← ngrok http 5000
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 5. Copy URL      │ ← https://abc123.ngrok.io/webhook
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 6. Meta Console  │ ← Paste URL + Same Token
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 7. Done! ✅      │ ← Webhook working
└──────────────────┘
```

---

## Example: Complete Setup

**My Verify Token:**
```
webhook_secret_abc123
```

**My .env file:**
```env
WEBHOOK_VERIFY_TOKEN=webhook_secret_abc123
```

**Start Apps:**
```bash
# Terminal 1
python app.py

# Terminal 2
ngrok http 5000
```

**Ngrok Output:**
```
Forwarding: https://1a2b3c4d.ngrok.io -> http://localhost:5000
```

**Meta Console Configuration:**
```
Callback URL: https://1a2b3c4d.ngrok.io/webhook
Verify Token: webhook_secret_abc123
```

**Test in Browser:**
```
https://1a2b3c4d.ngrok.io/webhook?hub.mode=subscribe&hub.verify_token=webhook_secret_abc123&hub.challenge=hello
```

**Expected:** Shows `hello`

**Done! ✅**

---

## Still Confused?

### Think of it Like This:

1. **Verify Token** = Your house key 🔑
2. **Webhook URL** = Your house address 🏠
3. **Meta Console** = Giving WhatsApp your address and a copy of your key
4. **Ngrok** = A tunnel that lets WhatsApp reach your local computer

When WhatsApp wants to send you data:
1. WhatsApp knocks on your door (webhook URL)
2. WhatsApp shows the key (verify token)
3. You check if it's the right key
4. If yes, you let them in and accept the data
5. If no, you close the door (reject)

**That's it! Simple! 🎉**

---

## Need Help?

**Check:**
1. .env file has the token
2. Flask app is running
3. Ngrok is running (for local)
4. Meta Console has correct URL and token
5. Token is EXACTLY the same in both places
6. URL includes `/webhook` at the end
7. Subscribed to `messages` and `message_status`

**Still stuck?**
- Check console logs for errors
- Test webhook URL in browser
- Make sure HTTPS (not HTTP)
- Restart everything and try again
