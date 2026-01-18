"""
Test Shopify Webhook with Sample Data
This simulates what Shopify sends to your webhook
"""

import requests
import json

# Your server URL
# Change this to your ngrok URL or public server URL
SERVER_URL = "http://localhost:5000"

# Sample abandoned checkout data from Shopify
# This is what Shopify actually sends for abandoned checkout
abandoned_checkout_sample = {
    "id": 123456789,
    "token": "abc123token",
    "cart_token": "def456cart",
    "email": "customer@example.com",
    "phone": "+1234567890",  # Or it might be in billing_address
    "note": "",
    "created_at": "2024-01-01T12:00:00-05:00",
    "updated_at": "2024-01-01T12:30:00-05:00",
    "completed_at": None,
    "abandoned_checkout_url": "https://your-store.myshopify.com/123456789/checkouts/abc123/recover",
    "line_items": [
        {
            "id": 111111,
            "variant_id": 222222,
            "title": "Cool Product",
            "quantity": 2,
            "price": "29.99",
            "vendor": "Your Store",
            "product_id": 333333
        },
        {
            "id": 444444,
            "variant_id": 555555,
            "title": "Another Product",
            "quantity": 1,
            "price": "49.99",
            "vendor": "Your Store",
            "product_id": 666666
        }
    ],
    "currency": "USD",
    "subtotal_price": "109.97",
    "total_price": "119.96",
    "total_tax": "9.99",
    "customer": {
        "id": 777777,
        "email": "customer@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "phone": "+1234567890",
        "default_address": {
            "phone": "+1234567890"
        }
    },
    "billing_address": {
        "first_name": "John",
        "last_name": "Doe",
        "phone": "+1234567890",
        "address1": "123 Main St",
        "city": "New York",
        "province": "NY",
        "country": "United States",
        "zip": "10001"
    }
}

# Sample order data from Shopify
order_sample = {
    "id": 999888777,
    "email": "customer@example.com",
    "phone": "+1234567890",
    "order_number": 1001,
    "name": "#1001",
    "financial_status": "paid",
    "fulfillment_status": "unfulfilled",
    "total_price": "119.96",
    "subtotal_price": "109.97",
    "total_tax": "9.99",
    "currency": "USD",
    "line_items": [
        {
            "id": 111111,
            "variant_id": 222222,
            "title": "Cool Product",
            "quantity": 2,
            "price": "29.99"
        },
        {
            "id": 444444,
            "variant_id": 555555,
            "title": "Another Product",
            "quantity": 1,
            "price": "49.99"
        }
    ],
    "customer": {
        "id": 777777,
        "email": "customer@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "phone": "+1234567890"
    },
    "cart_token": "def456cart"
}

print("=" * 60)
print("🧪 TESTING SHOPIFY WEBHOOKS")
print("=" * 60)

# Test 1: Abandoned Cart
print("\n🛒 Test 1: Abandoned Cart Webhook")
print("-" * 60)
try:
    response = requests.post(
        f"{SERVER_URL}/shopify/webhook/cart-create",
        json=abandoned_checkout_sample,
        headers={"Content-Type": "application/json"},
        timeout=10
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        print("✅ Abandoned cart webhook successful!")
    else:
        print(f"❌ Webhook failed with status {response.status_code}")
        
except requests.exceptions.ConnectionError:
    print("❌ Connection Error - Is the server running?")
    print("   Start server: python app.py")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 2: Order Creation
print("\n📦 Test 2: Order Creation Webhook")
print("-" * 60)
try:
    response = requests.post(
        f"{SERVER_URL}/shopify/webhook/order-create",
        json=order_sample,
        headers={"Content-Type": "application/json"},
        timeout=10
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        print("✅ Order webhook successful!")
    else:
        print(f"❌ Webhook failed with status {response.status_code}")
        
except requests.exceptions.ConnectionError:
    print("❌ Connection Error - Is the server running?")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 60)
print("📝 NEXT STEPS")
print("=" * 60)
print("""
If webhooks succeeded:
1. Check server logs for:
   - "🛒 Abandoned cart webhook received"
   - "📦 Order webhook received"
   
2. Run the debug script to verify data was stored:
   python debug_abandoned_cart.py

3. Go to dashboard and click automation buttons to send messages

If webhooks failed:
1. Make sure server is running (python app.py)
2. Check server logs for errors
3. Verify database tables exist
4. Try running: python debug_abandoned_cart.py first
""")

print("\n💡 TIP: To test with ngrok:")
print(f"   1. Run: ngrok http 5000")
print(f"   2. Update SERVER_URL in this script to your ngrok URL")
print(f"   3. Run this script again")
print("=" * 60)
