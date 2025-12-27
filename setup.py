#!/usr/bin/env python3
"""
Setup script for WhatsApp Dashboard
Helps with initial configuration and validation
"""

import os
import secrets
import sys

def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")

def generate_secret_key():
    """Generate a secure random secret key"""
    return secrets.token_hex(32)

def check_env_file():
    """Check if .env file exists"""
    if os.path.exists('.env'):
        print("✅ .env file found")
        return True
    else:
        print("❌ .env file not found")
        return False

def create_env_from_example():
    """Copy .env.example to .env"""
    if os.path.exists('.env.example'):
        with open('.env.example', 'r') as example:
            content = example.read()
        
        # Generate new secret key
        new_secret = generate_secret_key()
        content = content.replace('your_super_secret_key_here_change_in_production', new_secret)
        
        with open('.env', 'w') as env_file:
            env_file.write(content)
        
        print("✅ Created .env file from .env.example")
        print(f"✅ Generated SECRET_KEY: {new_secret[:20]}...")
        return True
    else:
        print("❌ .env.example not found")
        return False

def validate_env_vars():
    """Validate that required environment variables are set"""
    from dotenv import load_dotenv
    load_dotenv()
    
    required_vars = [
        'WHATSAPP_ACCESS_TOKEN',
        'WHATSAPP_PHONE_NUMBER_ID',
        'WABA_ID',
        'SECRET_KEY'
    ]
    
    missing = []
    placeholder_values = [
        'your_access_token_here',
        'your_phone_number_id_here',
        'your_whatsapp_business_account_id_here',
        'your_super_secret_key_here_change_in_production'
    ]
    
    for var in required_vars:
        value = os.getenv(var)
        if not value or value in placeholder_values:
            missing.append(var)
    
    if missing:
        print("\n❌ Missing or placeholder values for:")
        for var in missing:
            print(f"   - {var}")
        return False
    else:
        print("\n✅ All required environment variables are set")
        return True

def main():
    """Main setup function"""
    print_header("WhatsApp Dashboard Setup")
    
    print("This script will help you set up your WhatsApp Dashboard.\n")
    
    # Step 1: Check/create .env file
    print("Step 1: Checking environment file...")
    if not check_env_file():
        print("\nWould you like to create .env from .env.example? (y/n): ", end='')
        choice = input().strip().lower()
        if choice == 'y':
            if not create_env_from_example():
                print("\n❌ Failed to create .env file")
                sys.exit(1)
        else:
            print("\n❌ Setup cancelled. Please create .env file manually.")
            sys.exit(1)
    
    # Step 2: Validate environment variables
    print("\nStep 2: Validating environment variables...")
    if not validate_env_vars():
        print("\n⚠️  Please edit .env file and fill in your WhatsApp API credentials")
        print("    Get them from: https://business.facebook.com/")
        print("    WhatsApp > API Setup")
        sys.exit(1)
    
    # Step 3: Check dependencies
    print("\nStep 3: Checking dependencies...")
    try:
        import flask
        import pandas
        import requests
        print("✅ All required packages are installed")
    except ImportError as e:
        print(f"❌ Missing package: {e.name}")
        print("   Run: pip install -r requirements.txt")
        sys.exit(1)
    
    # Success
    print_header("Setup Complete!")
    print("✅ Your WhatsApp Dashboard is ready to use!\n")
    print("To start the application, run:")
    print("   python app.py\n")
    print("Then open your browser to:")
    print("   http://127.0.0.1:5000\n")
    print("For production deployment, see SECURITY_FIXES.md\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during setup: {e}")
        sys.exit(1)
