# Cart Abandonment & Order Confirmation Setup Guide

## Overview
Automatically send WhatsApp messages to customers who abandon their carts or place orders through your Shopify store.

## Features

### 1. **Abandoned Cart Reminders**
- Automatically track when customers add items to cart but don't complete purchase
- Send personalized WhatsApp reminders with cart details
- Include product names and total price
- Track which reminders have been sent

### 2. **Order Confirmations**
- Automatically detect new orders from Shopify
- Send instant WhatsApp confirmation with order details
- Include order number, products, and total
- Mark carts as recovered when orders are placed

## Setup Instructions

### Step 1: Configure Shopify Webhooks

You need to set up two webhooks in your Shopify store:

#### A. Abandoned Cart Webhook
1. Go to **Shopify Admin** → **Settings** → **Notifications**
2. Scroll to **Webhooks** section
3. Click **Create webhook**
4. Configure:
   - **Event:** `Checkout created`
   - **Format:** `JSON`
   - **URL:** `https://your-domain.com/shopify/webhook/cart-create`
   - **Webhook API version:** `2024-01`

#### B. Order Created Webhook
1. In the same Webhooks section
2. Click **Create webhook**
3. Configure:
   - **Event:** `Order creation`
   - **Format:** `JSON`
   - **URL:** `https://your-domain.com/shopify/webhook/order-create`
   - **Webhook API version:** `2024-01`

### Step 2: Expose Your Server (for local development)

If running locally, use ngrok to expose your server:

```bash
ngrok http 5000
```

This will give you a URL like: `https://abc123.ngrok.io`

Use this URL in your Shopify webhooks:
- Cart webhook: `https://abc123.ngrok.io/shopify/webhook/cart-create`
- Order webhook: `https://abc123.ngrok.io/shopify/webhook/order-create`

### Step 3: Ensure Database Tables Exist

The tables are created automatically when you run the app. To verify:

```python
python app.py
```

Check logs for:
```
✅ Database initialized
```

### Step 4: Test the Integration

#### Test Abandoned Cart:
1. Go to your Shopify store
2. Add products to cart
3. Fill in email and phone number at checkout
4. **Don't complete the purchase** - close the page
5. Check your dashboard logs for: `🛒 Abandoned cart webhook received`

#### Test Order Creation:
1. Complete a purchase on your Shopify store
2. Include a phone number in the order
3. Check logs for: `📦 Order webhook received: Order #XXXX`

## How to Use

### Sending Cart Reminders

#### Option 1: Manual Trigger from Dashboard
1. Go to home page of WhatsApp Dashboard
2. Click **"Send Cart Reminders"** button under Automation
3. System will send messages to all customers with unsent cart reminders

#### Option 2: API Call
```bash
POST /api/send-cart-reminders
Authorization: Bearer <your-session-token>
```

Response:
```json
{
  "success": true,
  "sent": 5,
  "failed": 0,
  "message": "Sent 5 cart reminders"
}
```

### Sending Order Confirmations

#### Option 1: Manual Trigger from Dashboard
1. Go to home page
2. Click **"Send Order Confirmations"** button
3. System will send confirmations for all unsent orders

#### Option 2: API Call
```bash
POST /api/send-order-confirmations
Authorization: Bearer <your-session-token>
```

## Message Templates

### Cart Reminder Message
```
Hi! 👋

You left some items in your cart:

• Product Name 1
• Product Name 2
• Product Name 3
...and 2 more items

Total: $150.00

Complete your purchase now! 🛒✨
```

### Order Confirmation Message
```
✅ Order Confirmed! 

Order #1234

• Product Name 1 x1
• Product Name 2 x2
• Product Name 3 x1

Total: $200.00

Thank you for your purchase! 🎉
We'll send you updates on your order.
```

## Database Schema

### `abandoned_carts` Table
```sql
- id: Primary key
- user_id: User who owns this cart
- shopify_cart_id: Unique cart ID from Shopify
- customer_id: Shopify customer ID
- customer_email: Customer email
- customer_phone: Customer phone (required for WhatsApp)
- cart_token: Unique cart token
- cart_items: JSON array of products
- total_price: Cart total
- currency: Currency code
- abandoned_at: When cart was abandoned
- reminder_sent: Boolean flag
- reminder_sent_at: When reminder was sent
- recovered: Whether cart was converted to order
- recovered_at: When cart was recovered
```

### `shopify_orders` Table
```sql
- id: Primary key
- user_id: User who owns this order
- shopify_order_id: Unique order ID from Shopify
- order_number: Human-readable order number
- customer_id: Shopify customer ID
- customer_email: Customer email
- customer_phone: Customer phone
- total_price: Order total
- currency: Currency code
- financial_status: Payment status
- fulfillment_status: Shipping status
- order_items: JSON array of products
- confirmation_sent: Boolean flag
- confirmation_sent_at: When confirmation was sent
```

## Automation Options

### Scheduled Automation
You can set up a cron job or scheduled task to automatically send messages:

#### Every hour - Send cart reminders
```bash
# Linux cron (add to crontab -e)
0 * * * * curl -X POST http://localhost:5000/api/send-cart-reminders

# Windows Task Scheduler
schtasks /create /tn "CartReminders" /tr "curl -X POST http://localhost:5000/api/send-cart-reminders" /sc hourly
```

#### On order creation - Instant confirmation
Messages are sent immediately when you click the button. For auto-send on webhook receipt, you could modify the webhook handler to send immediately.

## Customization

### Customize Messages

Edit the message templates in `app.py`:

**Cart Reminder** (line ~1470):
```python
message = f"""Hi! 👋

You left some items in your cart:

{product_list}

Total: {cart.get('currency', '$')}{cart.get('total_price', '0')}

Complete your purchase now! 🛒✨"""
```

**Order Confirmation** (line ~1540):
```python
message = f"""✅ Order Confirmed! 

Order #{order['order_number']}

{product_list}

Total: {order.get('currency', '$')}{order.get('total_price', '0')}

Thank you for your purchase! 🎉
We'll send you updates on your order."""
```

### Add Time Delay for Cart Reminders

To wait X hours before sending cart reminder, modify the query in `get_unsent_cart_reminders()`:

```python
# database.py - add time filter
cursor.execute('''
    SELECT * FROM abandoned_carts 
    WHERE user_id = ? 
    AND reminder_sent = 0 
    AND recovered = 0
    AND customer_phone IS NOT NULL 
    AND customer_phone != ""
    AND abandoned_at < datetime('now', '-2 hours')  -- Wait 2 hours
    ORDER BY abandoned_at DESC
''', (user_id,))
```

## Troubleshooting

### No Webhooks Received

**Check 1: Webhook URL is correct**
- Must be publicly accessible
- Use ngrok for local development
- Verify HTTPS (Shopify requires HTTPS)

**Check 2: Shopify webhook status**
- Go to Shopify Admin → Settings → Notifications
- Check webhook status (should show green checkmark)
- Click webhook to see recent deliveries

**Check 3: Server logs**
```bash
# Should see these lines when webhook fires:
🛒 Abandoned cart webhook received
✅ Abandoned cart stored: 123
```

### Phone Numbers Not Found

**Problem:** Customers don't have phone numbers

**Solution:**
1. Make phone number required at checkout
2. Shopify Settings → Checkout → Customer contact → Phone required
3. Existing customers won't have phone - they'll be skipped

### Messages Not Sending

**Check 1: Phone number format**
- Must include country code
- Format: +1234567890 or 1234567890
- See phone number formatting in utils/whatsapp.py

**Check 2: WhatsApp API limits**
- Check rate limits in .env
- View Queue Monitor on dashboard
- Check error logs

**Check 3: Customer phone exists**
```sql
-- Check database
SELECT customer_phone FROM abandoned_carts WHERE customer_phone IS NOT NULL;
SELECT customer_phone FROM shopify_orders WHERE customer_phone IS NOT NULL;
```

### Testing Without Real Shopify Store

Create test data manually:

```python
# test_automation.py
from utils.database import Database
import json

db = Database()

# Test abandoned cart
cart_data = {
    'id': '12345',
    'customer_id': '67890',
    'email': 'test@example.com',
    'phone': '+1234567890',
    'token': 'abc123',
    'line_items': [
        {'title': 'Test Product', 'quantity': 1, 'price': '50.00'}
    ],
    'total_price': '50.00',
    'currency': 'USD',
    'abandoned_checkout_url': 'https://store.com/cart'
}

db.add_abandoned_cart('user_id_here', cart_data)
print("✅ Test cart added")

# Test order
order_data = {
    'id': '54321',
    'order_number': '1001',
    'customer': {'id': '67890'},
    'email': 'test@example.com',
    'phone': '+1234567890',
    'total_price': '50.00',
    'currency': 'USD',
    'financial_status': 'paid',
    'fulfillment_status': 'unfulfilled',
    'line_items': [
        {'title': 'Test Product', 'quantity': 1}
    ]
}

db.add_order('user_id_here', order_data)
print("✅ Test order added")
```

Then run:
```bash
python test_automation.py
```

Go to dashboard and click the automation buttons to send test messages.

## Best Practices

1. **Timing:** Wait 2-4 hours before sending cart reminders
2. **Frequency:** Don't send multiple reminders for same cart
3. **Personalization:** Use customer name if available
4. **Incentives:** Consider adding discount codes
5. **Tracking:** Monitor recovery rate in analytics
6. **Compliance:** Ensure customers opted in for WhatsApp messages
7. **Testing:** Always test with your own phone first

## Future Enhancements

Potential features to add:
- Multiple cart reminder sequences (2h, 24h, 48h)
- A/B testing different message templates
- Add discount codes to cart reminders
- Track conversion rate from reminders
- Send shipping updates for orders
- Send delivery confirmation
- Request reviews after delivery
