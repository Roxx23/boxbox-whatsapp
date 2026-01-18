"""Quick test to verify Shopify sync with detailed logging"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Add the current directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.shopify_integration import ShopifyIntegration
import config

print("="*60)
print("QUICK SHOPIFY SYNC TEST")
print("="*60)

# Check credentials
print(f"\nShop Name: {config.SHOPIFY_SHOP_NAME}")
print(f"Has Access Token: {bool(config.SHOPIFY_ACCESS_TOKEN)}")

if not config.SHOPIFY_SHOP_NAME or not config.SHOPIFY_ACCESS_TOKEN:
    print("\n❌ ERROR: Shopify credentials not configured in .env file!")
    sys.exit(1)

print("\n✅ Credentials found, fetching customers...\n")

# Create Shopify integration
shopify = ShopifyIntegration(config.SHOPIFY_SHOP_NAME, config.SHOPIFY_ACCESS_TOKEN)

# Fetch customers
customers = shopify.fetch_customers()

print(f"\n{'='*60}")
print(f"FETCHED {len(customers)} CUSTOMERS")
print(f"{'='*60}\n")

if not customers:
    print("❌ No customers found in Shopify!")
    print("Make sure you have customers in your Shopify store.")
    sys.exit(0)

# Process each customer
synced_count = 0
skipped_count = 0

for i, customer in enumerate(customers, 1):
    print(f"\n--- Customer {i} ---")
    print(f"Raw Shopify Data:")
    print(f"  ID: {customer.get('id')}")
    print(f"  Name: {customer.get('first_name')} {customer.get('last_name')}")
    print(f"  Email: {customer.get('email')}")
    print(f"  Phone (direct): '{customer.get('phone')}'")
    print(f"  Phone (address): '{customer.get('default_address', {}).get('phone')}'")
    
    # Parse customer data
    customer_data = shopify.parse_customer_data(customer)
    
    print(f"\nParsed Data:")
    print(f"  First Name: '{customer_data['first_name']}'")
    print(f"  Last Name: '{customer_data['last_name']}'")
    print(f"  Email: '{customer_data['email']}'")
    print(f"  Phone: '{customer_data['phone']}'")
    print(f"  Phone is truthy: {bool(customer_data['phone'])}")
    
    if customer_data['phone']:
        print(f"✅ WOULD BE SYNCED")
        synced_count += 1
    else:
        print(f"❌ WOULD BE SKIPPED (no phone)")
        skipped_count += 1

print(f"\n{'='*60}")
print(f"SUMMARY")
print(f"{'='*60}")
print(f"Total customers: {len(customers)}")
print(f"Would sync: {synced_count}")
print(f"Would skip: {skipped_count}")
print(f"{'='*60}\n")

if skipped_count > 0:
    print("⚠️ Some customers don't have phone numbers!")
    print("Add phone numbers in Shopify Admin to sync them.")
