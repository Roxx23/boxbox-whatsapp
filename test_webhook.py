"""Test webhook verification"""
import os
from dotenv import load_dotenv
import requests

load_dotenv()

print("="*60)
print("WEBHOOK VERIFICATION TEST")
print("="*60)

# Check environment variable
verify_token = os.getenv("WEBHOOK_VERIFY_TOKEN")
print(f"\n1. WEBHOOK_VERIFY_TOKEN in .env: {verify_token}")

if not verify_token:
    print("\n❌ ERROR: WEBHOOK_VERIFY_TOKEN not found in .env file!")
    print("\nAdd this to your .env file:")
    print("WEBHOOK_VERIFY_TOKEN=your_secret_token_here")
    exit(1)

print(f"   Token length: {len(verify_token)}")
print(f"   Token: '{verify_token}'")

# Check if Flask app is running
print("\n2. Testing if Flask app is running...")
try:
    response = requests.get("http://localhost:5000/", timeout=3)
    print("   ✅ Flask app is running")
except Exception as e:
    print(f"   ❌ Flask app is NOT running: {e}")
    print("\n   Start Flask app first:")
    print("   python app.py")
    exit(1)

# Test webhook endpoint
print("\n3. Testing webhook verification endpoint...")
test_url = f"http://localhost:5000/webhook?hub.mode=subscribe&hub.verify_token={verify_token}&hub.challenge=test123"
print(f"   URL: {test_url}")

try:
    response = requests.get(test_url, timeout=5)
    print(f"   Status Code: {response.status_code}")
    print(f"   Response: {response.text}")
    
    if response.status_code == 200 and response.text == "test123":
        print("\n   ✅ Webhook verification WORKS!")
    elif response.status_code == 403:
        print("\n   ❌ Webhook verification FAILED!")
        print("   Token mismatch - check your .env file")
    else:
        print(f"\n   ⚠️ Unexpected response: {response.status_code}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test with wrong token
print("\n4. Testing with WRONG token (should fail)...")
wrong_url = "http://localhost:5000/webhook?hub.mode=subscribe&hub.verify_token=WRONG_TOKEN&hub.challenge=test123"
try:
    response = requests.get(wrong_url, timeout=5)
    if response.status_code == 403:
        print("   ✅ Correctly rejected wrong token")
    else:
        print(f"   ⚠️ Unexpected: {response.status_code}")
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "="*60)
print("NGROK SETUP INSTRUCTIONS")
print("="*60)
print("\n5. Start ngrok in another terminal:")
print("   ngrok http 5000")
print("\n6. Copy the HTTPS URL (e.g., https://abc123.ngrok.io)")
print("\n7. Test ngrok webhook:")
print("   Replace YOUR_NGROK_URL with your actual ngrok URL:")
print(f"   https://YOUR_NGROK_URL/webhook?hub.mode=subscribe&hub.verify_token={verify_token}&hub.challenge=test123")
print("\n8. Use in Meta Console:")
print("   Callback URL: https://YOUR_NGROK_URL/webhook")
print(f"   Verify Token: {verify_token}")
print("\n" + "="*60)
