# Troubleshooting Abandoned Cart Messages

## Quick Diagnosis

Run these scripts in order:

### 1. Check Database & Setup
```bash
python debug_abandoned_cart.py
```

This will check:
- ✅ Database tables exist
- ✅ Users exist
- ✅ Can insert test cart
- ✅ Can retrieve unsent carts

### 2. Test Webhook Locally
```bash
python test_abandoned_cart_webhook.py
```

This will:
- Send test webhook data to your server
- Verify webhook endpoints work
- Check if data is being stored

## Common Issues & Solutions

### Issue 1: "Not receiving webhooks from Shopify"

**Symptoms:**
- No logs showing "🛒 Abandoned cart webhook received"
- Database has no abandoned carts

**Solutions:**

#### A. Server not accessible
```bash
# Check if server is running
# You should see:
# * Running on http://127.0.0.1:5000

# If running locally, expose with ngrok:
ngrok http 5000

# Copy the HTTPS URL (e.g., https://abc123.ngrok.io)
```

#### B. Wrong webhook URL in Shopify
1. Go to **Shopify Admin** → **Settings** → **Notifications**
2. Scroll to **Webhooks**
3. Check/Create webhook:
   - **Event:** `Checkouts create` (not "Cart create")
   - **URL:** `https://your-ngrok-url.ngrok.io/shopify/webhook/cart-create`
   - **Format:** JSON

**Important:** Shopify webhook event should be:
- ✅ `Checkouts create` or `Checkouts update`
- ❌ NOT "Cart create" (that's something different)

#### C. Verify webhook in Shopify
1. Go to your webhook in Shopify
2. Click on it to see details
3. Check "Recent Deliveries" section
4. Look for:
   - ✅ Green checkmark = Success
   - ❌ Red X = Failed (click to see error)

### Issue 2: "Webhook received but no phone number"

**Symptoms:**
- Logs show: "🛒 Abandoned cart webhook received"
- Logs show: "⚠️ Cart has no phone number"

**Solutions:**

#### A. Make phone required at checkout
1. Go to **Shopify Admin** → **Settings** → **Checkout**
2. Find "Customer contact"
3. Enable: ☑️ **Require phone number**

#### B. Test with phone number
1. Go to your store
2. Add products to cart
3. Click "Checkout"
4. **IMPORTANT:** Enter phone number in the form
5. Close the browser (abandon checkout)
6. Wait 2-3 minutes
7. Check logs for phone number

### Issue 3: "Data stored but messages not sending"

**Symptoms:**
- `python debug_abandoned_cart.py` shows carts in database
- Click "Send Cart Reminders" but nothing happens

**Solutions:**

#### A. Check phone number format
```bash
python debug_abandoned_cart.py
```

Look for the phone number in the output. Should be:
- ✅ `+1234567890` (with country code)
- ✅ `1234567890` (digits only)
- ❌ `(123) 456-7890` (formatted - might not work)

#### B. Check WhatsApp API credentials
```bash
# In .env file, verify:
WHATSAPP_ACCESS_TOKEN=your_token_here
WHATSAPP_PHONE_NUMBER_ID=your_phone_id_here
```

#### C. Test WhatsApp API manually
```python
from utils.whatsapp import send_text

# Test with your phone
status, response = send_text("+1234567890", "Test message")
print(f"Status: {status}")
print(f"Response: {response}")
```

### Issue 4: "Messages sent but not received"

**Possible causes:**
1. Phone number invalid/not registered on WhatsApp
2. WhatsApp template not approved
3. Rate limiting (too many messages)

**Check:**
```bash
# View queue status
# Go to dashboard → look at Queue Monitor
```

## Step-by-Step Testing Process

### Test 1: Local Webhook Test
```bash
# Terminal 1: Start server
python app.py

# Terminal 2: Send test webhook
python test_abandoned_cart_webhook.py

# Expected output:
# ✅ Abandoned cart webhook successful!
```

### Test 2: Check Database
```bash
python debug_abandoned_cart.py

# Expected output:
# ✅ Found 1 unsent cart(s)
# Phone: +1234567890
```

### Test 3: Send Message
1. Go to `http://localhost:5000`
2. Login
3. Click "Send Cart Reminders"
4. Check result message

### Test 4: Real Shopify Test
```bash
# Terminal 1: Start ngrok
ngrok http 5000

# Terminal 2: Start server
python app.py

# Browser:
# 1. Update Shopify webhook URL to ngrok URL
# 2. Go to your store
# 3. Add product to cart
# 4. Enter phone at checkout
# 5. Close browser
# 6. Wait 2-3 minutes
# 7. Check server logs
```

## What to Look for in Logs

### Successful webhook:
```
🛒 Abandoned cart webhook received
📞 Extracted phone: +1234567890
📋 Cart data prepared: Phone=+1234567890, Email=test@test.com, Items=2
✅ Abandoned cart stored: 1
```

### Missing phone:
```
🛒 Abandoned cart webhook received
📞 Extracted phone: None
📋 Cart data prepared: Phone=None, Email=test@test.com, Items=2
⚠️  Cart 1 has no phone number - won't be able to send reminder
```

### No webhook received:
```
(No logs at all)
```

## Manual Testing Without Shopify

If you don't have a Shopify store or want to test quickly:

```python
# Create test_manual_cart.py
from utils.database import Database
from utils.auth import UserManager
import json

db = Database()
users = UserManager().get_all_users()

if users:
    cart_data = {
        'id': '999999',
        'customer_id': 'test',
        'email': 'test@test.com',
        'phone': '+1234567890',  # YOUR PHONE HERE
        'token': 'test123',
        'line_items': [
            {
                'title': 'Test Product 1',
                'quantity': 2,
                'price': '29.99'
            },
            {
                'title': 'Test Product 2',
                'quantity': 1,
                'price': '49.99'
            }
        ],
        'total_price': '109.97',
        'currency': 'USD',
        'abandoned_checkout_url': 'https://store.com/cart'
    }
    
    cart_id = db.add_abandoned_cart(users[0].id, cart_data)
    print(f"✅ Test cart created: {cart_id}")
    print("Go to dashboard and click 'Send Cart Reminders'")
```

Run:
```bash
python test_manual_cart.py
```

## Shopify Webhook Configuration

### Correct Configuration:

**Event:** Checkouts create  
**Format:** JSON  
**URL:** `https://your-server.com/shopify/webhook/cart-create`  
**API Version:** 2024-01  

### How to verify webhook is working:

1. Create a test checkout in your store
2. In Shopify Admin → Settings → Notifications → Webhooks
3. Click on your webhook
4. Check "Recent deliveries"
5. You should see attempts with timestamps
6. Green ✅ = Success
7. Red ❌ = Click to see error details

## Still Not Working?

Contact checklist:
1. ✅ Server is running
2. ✅ ngrok is running (for local)
3. ✅ Webhook URL is correct in Shopify
4. ✅ Webhook event is "Checkouts create"
5. ✅ Phone number entered at checkout
6. ✅ Logs show webhook received
7. ✅ Database has cart with phone number
8. ✅ WhatsApp API credentials are correct
9. ✅ Click "Send Cart Reminders" button

If all checked and still not working, check:
- Server error logs
- Shopify webhook delivery logs
- WhatsApp API response in logs
