"""
Debug script for abandoned cart feature
Run this to check if everything is set up correctly
"""

import sys
import json
from utils.database import Database
from utils.auth import UserManager

print("=" * 60)
print("🔍 ABANDONED CART DEBUGGING")
print("=" * 60)

# Initialize
db = Database()
user_manager = UserManager()

# Check 1: Database tables exist
print("\n📊 Check 1: Database Tables")
try:
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='abandoned_carts'")
        if cursor.fetchone():
            print("✅ abandoned_carts table exists")
        else:
            print("❌ abandoned_carts table NOT found")
            
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='shopify_orders'")
        if cursor.fetchone():
            print("✅ shopify_orders table exists")
        else:
            print("❌ shopify_orders table NOT found")
except Exception as e:
    print(f"❌ Error checking tables: {e}")

# Check 2: Users exist
print("\n👥 Check 2: Users")
try:
    users = user_manager.get_all_users()
    if users:
        print(f"✅ Found {len(users)} user(s):")
        for user in users:
            print(f"   - {user.username} (ID: {user.id})")
    else:
        print("❌ No users found - webhooks won't store data")
except Exception as e:
    print(f"❌ Error getting users: {e}")

# Check 3: Can we insert test cart?
print("\n🛒 Check 3: Test Cart Insertion")
try:
    users = user_manager.get_all_users()
    if users:
        test_cart = {
            'id': '999999999',
            'customer_id': 'test_customer',
            'email': 'test@example.com',
            'phone': '+1234567890',
            'token': 'test_token_123',
            'line_items': [
                {'title': 'Test Product', 'quantity': 1, 'price': '50.00'}
            ],
            'total_price': '50.00',
            'currency': 'USD',
            'abandoned_checkout_url': 'https://store.com/cart/test'
        }
        
        cart_id = db.add_abandoned_cart(users[0].id, test_cart)
        print(f"✅ Test cart inserted with ID: {cart_id}")
        
        # Verify it was stored
        carts = db.get_unsent_cart_reminders(users[0].id)
        print(f"✅ Found {len(carts)} unsent cart(s)")
        
        if carts:
            print("\n📋 Cart Details:")
            for cart in carts:
                print(f"   - Cart ID: {cart['id']}")
                print(f"   - Phone: {cart['customer_phone']}")
                print(f"   - Email: {cart['customer_email']}")
                print(f"   - Total: {cart['currency']}{cart['total_price']}")
                
                # Show items
                items = json.loads(cart['cart_items']) if cart['cart_items'] else []
                print(f"   - Items: {len(items)}")
                for item in items:
                    print(f"      • {item.get('title', 'Unknown')}")
    else:
        print("❌ No users - can't insert test cart")
        
except Exception as e:
    print(f"❌ Error inserting test cart: {e}")
    import traceback
    traceback.print_exc()

# Check 4: Webhook endpoint accessible
print("\n🌐 Check 4: Webhook Endpoints")
print("   Cart webhook: POST /shopify/webhook/cart-create")
print("   Order webhook: POST /shopify/webhook/order-create")
print("\n   Test locally with:")
print("   curl -X POST http://localhost:5000/shopify/webhook/cart-create \\")
print("        -H 'Content-Type: application/json' \\")
print("        -d '{\"id\":\"12345\",\"email\":\"test@test.com\",\"phone\":\"+1234567890\"}'")

# Check 5: Can we send messages?
print("\n📨 Check 5: Message Sending")
try:
    users = user_manager.get_all_users()
    if users:
        unsent = db.get_unsent_cart_reminders(users[0].id)
        if unsent:
            print(f"✅ Ready to send {len(unsent)} cart reminder(s)")
            print("   Go to dashboard and click 'Send Cart Reminders'")
        else:
            print("⚠️  No unsent carts found")
            print("   Add items to cart on Shopify and abandon checkout")
    else:
        print("❌ No users")
except Exception as e:
    print(f"❌ Error: {e}")

# Summary
print("\n" + "=" * 60)
print("📝 SUMMARY")
print("=" * 60)
print("""
To receive abandoned cart webhooks:

1. ✅ Database tables are set up (checked above)
2. ✅ Users exist (checked above)
3. 🌐 Expose your server publicly:
   
   For local testing:
   - Run: ngrok http 5000
   - Copy the HTTPS URL (e.g., https://abc123.ngrok.io)

4. 🔗 Configure Shopify webhook:
   
   Shopify Admin → Settings → Notifications → Webhooks
   - Event: "Checkout created" or "Abandoned checkouts"
   - Format: JSON
   - URL: https://your-ngrok-url.ngrok.io/shopify/webhook/cart-create
   - Version: 2024-01

5. 🧪 Test the webhook:
   
   Option A: Real test
   - Go to your Shopify store
   - Add products to cart
   - Enter email and phone at checkout
   - Close browser (abandon cart)
   - Wait a few minutes
   - Check server logs for: "🛒 Abandoned cart webhook received"
   
   Option B: Manual webhook test
   - Use curl command above
   - Or use Shopify webhook testing tool

6. 📤 Send reminders:
   - Go to dashboard
   - Click "Send Cart Reminders" button
   - Messages will be sent via WhatsApp

Common Issues:
- ❌ Webhook not received: Check ngrok is running, URL is correct
- ❌ No phone number: Customer must enter phone at checkout
- ❌ Messages not sending: Check WhatsApp API credentials in .env
""")

print("=" * 60)
