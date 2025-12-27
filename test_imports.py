"""
Quick test to verify all imports work and check for syntax errors
"""

print("Testing imports...")

try:
    print("1. Testing utils.whatsapp...")
    from utils.whatsapp import send_text, get_templates, send_template, upload_media
    print("   ✅ utils.whatsapp imported successfully")
except Exception as e:
    print(f"   ❌ Error importing utils.whatsapp: {e}")
    import traceback
    traceback.print_exc()

try:
    print("\n2. Testing config values...")
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
    PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    WABA_ID = os.getenv("WABA_ID")
    SECRET_KEY = os.getenv("SECRET_KEY")
    
    print(f"   ACCESS_TOKEN: {'✅ Set' if ACCESS_TOKEN else '❌ Missing'}")
    print(f"   PHONE_NUMBER_ID: {'✅ Set' if PHONE_NUMBER_ID else '❌ Missing'}")
    print(f"   WABA_ID: {'✅ Set' if WABA_ID else '❌ Missing'}")
    print(f"   SECRET_KEY: {'✅ Set' if SECRET_KEY else '❌ Missing'}")
except Exception as e:
    print(f"   ❌ Error loading config: {e}")

try:
    print("\n3. Testing Flask app...")
    from flask import Flask
    print("   ✅ Flask imported successfully")
except Exception as e:
    print(f"   ❌ Error importing Flask: {e}")

try:
    print("\n4. Testing database...")
    from utils.database import Database
    db = Database()
    print("   ✅ Database initialized successfully")
except Exception as e:
    print(f"   ❌ Error with database: {e}")

try:
    print("\n5. Checking templates folder...")
    import os
    if os.path.exists("templates/index.html"):
        print("   ✅ templates/index.html exists")
    else:
        print("   ❌ templates/index.html not found")
except Exception as e:
    print(f"   ❌ Error checking templates: {e}")

print("\n" + "="*50)
print("Import test complete!")
print("="*50)
