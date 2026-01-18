"""
Check what phone numbers are stored in abandoned carts
"""

from utils.database import Database
from utils.auth import UserManager
import json

db = Database()
users = UserManager().get_all_users()

print("=" * 60)
print("🔍 CHECKING STORED ABANDONED CARTS")
print("=" * 60)

if not users:
    print("❌ No users found")
    exit()

user_id = users[0].id
print(f"✅ User: {users[0].username} (ID: {user_id})")

# Get all abandoned carts (including ones with reminders sent)
with db.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM abandoned_carts 
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 10
    ''', (user_id,))
    
    carts = [dict(row) for row in cursor.fetchall()]

if not carts:
    print("\n⚠️  No abandoned carts found")
    print("   Try abandoning a cart on your Shopify store")
else:
    print(f"\n📊 Found {len(carts)} abandoned cart(s):\n")
    
    for i, cart in enumerate(carts, 1):
        print(f"Cart #{i}:")
        print(f"  📧 Email: {cart['customer_email']}")
        print(f"  📞 Phone: {cart['customer_phone']}")
        print(f"  💰 Total: {cart['currency']}{cart['total_price']}")
        print(f"  📅 Created: {cart['created_at']}")
        print(f"  ✅ Reminder Sent: {bool(cart['reminder_sent'])}")
        
        # Parse and show items
        if cart['cart_items']:
            items = json.loads(cart['cart_items'])
            print(f"  🛒 Items ({len(items)}):")
            for item in items[:3]:
                title = item.get('title', 'Unknown')
                qty = item.get('quantity', 1)
                print(f"     • {title} x{qty}")
            if len(items) > 3:
                print(f"     ... and {len(items) - 3} more")
        
        print()

print("=" * 60)
print("📝 ANALYSIS")
print("=" * 60)

# Check for common issues
for cart in carts:
    phone = cart['customer_phone']
    if not phone:
        print(f"❌ Cart ID {cart['id']}: No phone number")
    elif not phone.strip():
        print(f"❌ Cart ID {cart['id']}: Empty phone number")
    elif len(phone) < 10:
        print(f"⚠️  Cart ID {cart['id']}: Phone too short: '{phone}'")
    elif not phone.startswith('+') and not phone.startswith('91') and not phone.startswith('1'):
        print(f"⚠️  Cart ID {cart['id']}: Phone might be missing country code: '{phone}'")
    else:
        print(f"✅ Cart ID {cart['id']}: Phone looks good: '{phone}'")

print("\n" + "=" * 60)
print("💡 TIP:")
print("=" * 60)
print("""
If phone numbers look wrong:
1. Check your Shopify store checkout settings
2. Make sure phone field is visible and required
3. When testing, enter phone in international format: +1234567890
4. Check server logs for the webhook data to see what Shopify sends
""")
