"""Debug script to test Shopify API connection and customer fetching"""
import os
from dotenv import load_dotenv
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

SHOPIFY_SHOP_NAME = os.getenv("SHOPIFY_SHOP_NAME")
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")

print("=" * 60)
print("SHOPIFY CREDENTIALS CHECK")
print("=" * 60)
print(f"SHOPIFY_SHOP_NAME: {SHOPIFY_SHOP_NAME}")
print(f"SHOPIFY_ACCESS_TOKEN exists: {bool(SHOPIFY_ACCESS_TOKEN)}")
if SHOPIFY_ACCESS_TOKEN:
    print(f"SHOPIFY_ACCESS_TOKEN length: {len(SHOPIFY_ACCESS_TOKEN)}")
    print(f"SHOPIFY_ACCESS_TOKEN preview: {SHOPIFY_ACCESS_TOKEN[:20]}...")
print()

if not SHOPIFY_SHOP_NAME or not SHOPIFY_ACCESS_TOKEN:
    print("❌ ERROR: Shopify credentials not configured!")
    print("Please add the following to your .env file:")
    print("SHOPIFY_SHOP_NAME=your-store-name")
    print("SHOPIFY_ACCESS_TOKEN=your-access-token")
    exit(1)

print("=" * 60)
print("TESTING SHOPIFY API CONNECTION")
print("=" * 60)

base_url = f"https://{SHOPIFY_SHOP_NAME}.myshopify.com/admin/api/2024-01"
headers = {
    "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
    "Content-Type": "application/json"
}

# Test 1: Fetch shop info
print("\nTest 1: Fetching shop info...")
try:
    url = f"{base_url}/shop.json"
    print(f"URL: {url}")
    response = requests.get(url, headers=headers)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        shop_data = response.json()
        print(f"✅ Shop Name: {shop_data.get('shop', {}).get('name')}")
        print(f"✅ Shop Domain: {shop_data.get('shop', {}).get('domain')}")
    else:
        print(f"❌ Error: {response.text}")
except Exception as e:
    print(f"❌ Exception: {e}")

# Test 2: Fetch customers
print("\n" + "=" * 60)
print("Test 2: Fetching customers...")
print("=" * 60)
try:
    url = f"{base_url}/customers.json?limit=10"
    print(f"URL: {url}")
    response = requests.get(url, headers=headers)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        customers = data.get('customers', [])
        print(f"✅ Customers found: {len(customers)}")
        
        if customers:
            print("\nFirst customer details:")
            customer = customers[0]
            print(f"  ID: {customer.get('id')}")
            print(f"  Name: {customer.get('first_name')} {customer.get('last_name')}")
            print(f"  Email: {customer.get('email')}")
            print(f"  Phone: {customer.get('phone')}")
            print(f"  Total Spent: ${customer.get('total_spent')}")
            print(f"  Orders Count: {customer.get('orders_count')}")
            
            # Check pagination
            link_header = response.headers.get('Link', '')
            print(f"\nPagination Link Header: {link_header}")
        else:
            print("⚠️ No customers found in your Shopify store")
            print("Make sure you have customers in your store at:")
            print(f"https://{SHOPIFY_SHOP_NAME}.myshopify.com/admin/customers")
    elif response.status_code == 401:
        print("❌ Authentication failed!")
        print("Your access token is invalid or has expired.")
    elif response.status_code == 404:
        print("❌ Store not found!")
        print(f"Check that '{SHOPIFY_SHOP_NAME}' is the correct store name.")
    else:
        print(f"❌ Error: {response.text}")
except Exception as e:
    print(f"❌ Exception: {e}")

# Test 3: Check customer count
print("\n" + "=" * 60)
print("Test 3: Getting total customer count...")
print("=" * 60)
try:
    url = f"{base_url}/customers/count.json"
    print(f"URL: {url}")
    response = requests.get(url, headers=headers)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        count_data = response.json()
        count = count_data.get('count', 0)
        print(f"✅ Total customers in store: {count}")
        
        if count == 0:
            print("\n⚠️ Your Shopify store has 0 customers!")
            print("Add some customers to your store first.")
    else:
        print(f"❌ Error: {response.text}")
except Exception as e:
    print(f"❌ Exception: {e}")

print("\n" + "=" * 60)
print("DEBUG COMPLETE")
print("=" * 60)
