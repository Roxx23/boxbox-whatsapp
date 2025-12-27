"""
Test script for sending WhatsApp templates with button parameters.
This script helps you test templates with COPY_CODE buttons.
"""

import sys
import os
from dotenv import load_dotenv
from utils.whatsapp import send_template, get_templates

load_dotenv()
WABA_ID = os.getenv('WABA_ID')

# Validate WABA_ID
if not WABA_ID:
    print("❌ ERROR: WABA_ID not found in .env file")
    print("Please add WABA_ID=your_waba_id to your .env file")
    sys.exit(1)

def list_templates_with_buttons():
    """List all templates that have buttons"""
    print("\n" + "="*60)
    print("📋 TEMPLATES WITH BUTTONS")
    print("="*60)
    
    templates = get_templates(WABA_ID)
    
    templates_with_buttons = []
    for t in templates:
        buttons_component = next(
            (c for c in t["components"] if c["type"] == "BUTTONS"), 
            None
        )
        if buttons_component and "buttons" in buttons_component:
            templates_with_buttons.append(t)
            
            print(f"\n📌 Template: {t['name']}")
            print(f"   Language: {t.get('language', 'N/A')}")
            print(f"   Category: {t.get('category', 'N/A')}")
            print(f"   Status: {t.get('status', 'N/A')}")
            
            # Check for IMAGE header
            header = next((c for c in t["components"] if c["type"] == "HEADER"), None)
            if header and header.get('format') == 'IMAGE':
                print(f"   ⚠️  Has IMAGE header - requires header_media_id parameter")
            
            # Show body text
            body = next((c for c in t["components"] if c["type"] == "BODY"), None)
            if body:
                body_text = body.get('text', '')
                # Truncate if too long
                if len(body_text) > 100:
                    body_text = body_text[:100] + "..."
                print(f"   Body: {body_text}")
            
            print(f"   Buttons:")
            for idx, btn in enumerate(buttons_component["buttons"]):
                btn_type = btn.get('type', 'Unknown')
                btn_text = btn.get('text', 'No text')
                print(f"      {idx+1}. [{btn_type}] {btn_text}")
                
                # Show what parameter is needed
                if btn_type == "COPY_CODE":
                    print(f"         → Requires: coupon_code parameter")
                elif btn_type == "URL" and "{{1}}" in btn.get('url', ''):
                    print(f"         → Requires: URL parameter")
    
    if not templates_with_buttons:
        print("\n⚠️  No templates with buttons found.")
        print("   Make sure you have created templates with buttons in Meta Business Manager.")
    
    print("\n" + "="*60)
    return templates_with_buttons


def test_template_send():
    """Test sending a template with button parameters"""
    print("\n" + "="*60)
    print("🚀 TEST TEMPLATE WITH BUTTON PARAMETERS")
    print("="*60)
    
    # Configuration - EDIT THESE VALUES
    PHONE = "+919156143465"  # Your test phone number
    TEMPLATE_NAME = "your_template_name"  # Replace with actual template name
    COUPON_CODE = "SAVE20"  # Your coupon code
    BODY_PARAMS = []  # Add body parameters if your template has {{1}}, {{2}}, etc.
    LANGUAGE = "en_US"  # Template language code
    HEADER_IMAGE_ID = None  # Add media ID if template has IMAGE header
    
    print(f"\n📞 Phone: {PHONE}")
    print(f"📝 Template: {TEMPLATE_NAME}")
    print(f"🎫 Coupon Code: {COUPON_CODE}")
    print(f"🌍 Language: {LANGUAGE}")
    
    if BODY_PARAMS:
        print(f"📦 Body Params: {BODY_PARAMS}")
    
    if HEADER_IMAGE_ID:
        print(f"🖼️  Header Image ID: {HEADER_IMAGE_ID}")
    
    # Prepare button parameters
    button_params = {
        "copy_code": COUPON_CODE
    }
    
    print(f"\n🔧 Button Params: {button_params}")
    print("\n⏳ Sending...")
    
    try:
        status, response = send_template(
            number=PHONE,
            template_name=TEMPLATE_NAME,
            params=BODY_PARAMS,
            lang=LANGUAGE,
            header_media_id=HEADER_IMAGE_ID,
            button_params=button_params
        )
        
        print(f"\n📊 Status Code: {status}")
        
        if status == 200:
            print("✅ SUCCESS! Message sent successfully")
            print(f"📨 Response: {response}")
        else:
            print(f"❌ FAILED with status {status}")
            print(f"❌ Error: {response}")
            
            # Provide helpful error messages
            if status == 404:
                print("\n💡 Tip: Template not found. Check the template name is correct.")
            elif status == 400:
                error_msg = str(response)
                if "131008" in error_msg:
                    print("\n💡 Tip: Button parameter missing. Make sure button_params is set correctly.")
                elif "131009" in error_msg:
                    print("\n💡 Tip: Template parameters mismatch. Check body parameters.")
                elif "132012" in error_msg or "Format mismatch" in error_msg:
                    print("\n💡 Tip: Template format mismatch.")
                    if "expected IMAGE" in error_msg:
                        print("    Your template has an IMAGE header but no image was provided.")
                        print("    Solution: Provide header_media_id parameter with uploaded image ID.")
                        print("\n    To upload an image:")
                        print("    from utils.whatsapp import upload_media")
                        print("    media_id = upload_media(your_image_file)")
                        print("    Then use: header_media_id=media_id")
            elif status == 401:
                print("\n💡 Tip: Authorization failed. Check your ACCESS_TOKEN in .env")
    
    except Exception as e:
        print(f"\n❌ Exception occurred: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*60)


def interactive_test():
    """Interactive mode - prompts for values"""
    print("\n" + "="*60)
    print("🎮 INTERACTIVE MODE")
    print("="*60)
    
    # List templates first
    templates_with_buttons = list_templates_with_buttons()
    
    if not templates_with_buttons:
        print("\n❌ No templates with buttons found. Cannot proceed.")
        return
    
    print("\n" + "-"*60)
    
    # Get template name
    template_name = input("\n📝 Enter template name: ").strip()
    if not template_name:
        print("❌ Template name is required")
        return
    
    # Check if template has IMAGE header
    templates = get_templates(WABA_ID)
    selected_template = next((t for t in templates if t["name"] == template_name), None)
    has_image_header = False
    if selected_template:
        header = next((c for c in selected_template["components"] if c["type"] == "HEADER"), None)
        if header and header.get('format') == 'IMAGE':
            has_image_header = True
            print("\n⚠️  This template has an IMAGE header!")
            print("    You need to provide a header_media_id")
    
    # Get phone number
    phone = input("📞 Enter phone number (with country code, e.g., +919156143465): ").strip()
    if not phone:
        print("❌ Phone number is required")
        return
    
    # Get coupon code
    coupon_code = input("🎫 Enter coupon code (e.g., SAVE20): ").strip()
    if not coupon_code:
        print("❌ Coupon code is required")
        return
    
    # Get body parameters
    body_params_str = input("📦 Enter body parameters separated by comma (or press Enter if none): ").strip()
    body_params = []
    if body_params_str:
        body_params = [p.strip() for p in body_params_str.split(",")]
    
    # Get header image ID if needed
    header_media_id = None
    if has_image_header:
        header_media_id = input("🖼️  Enter header image media ID (or press Enter to skip): ").strip()
        if not header_media_id:
            print("\n⚠️  Warning: Sending without image will likely fail!")
            print("    To upload an image, see documentation on using upload_media()")
    
    # Get language
    language = input("🌍 Enter language code (default: en_US): ").strip()
    if not language:
        language = "en_US"
    
    print("\n" + "-"*60)
    print("📋 SUMMARY:")
    print(f"   Template: {template_name}")
    print(f"   Phone: {phone}")
    print(f"   Coupon Code: {coupon_code}")
    print(f"   Body Params: {body_params if body_params else 'None'}")
    if header_media_id:
        print(f"   Header Image ID: {header_media_id}")
    print(f"   Language: {language}")
    print("-"*60)
    
    confirm = input("\n✅ Send message? (y/n): ").strip().lower()
    if confirm != 'y':
        print("❌ Cancelled")
        return
    
    # Send
    print("\n⏳ Sending...")
    
    button_params = {"copy_code": coupon_code}
    
    try:
        status, response = send_template(
            number=phone,
            template_name=template_name,
            params=body_params,
            lang=language,
            header_media_id=header_media_id if header_media_id else None,
            button_params=button_params
        )
        
        print(f"\n📊 Status Code: {status}")
        
        if status == 200:
            print("✅ SUCCESS! Message sent successfully")
            print(f"📨 Response: {response}")
        else:
            print(f"❌ FAILED with status {status}")
            print(f"❌ Error: {response}")
    
    except Exception as e:
        print(f"\n❌ Exception occurred: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*60)


if __name__ == "__main__":
    print("\n" + "="*60)
    print("🔧 WHATSAPP BUTTON TEMPLATE TESTER")
    print("="*60)
    print("\nOptions:")
    print("1. List templates with buttons")
    print("2. Test send (edit script values)")
    print("3. Interactive test (prompts for values)")
    print("4. Exit")
    
    try:
        choice = input("\nSelect option (1-4): ").strip()
        
        if choice == "1":
            list_templates_with_buttons()
        elif choice == "2":
            test_template_send()
        elif choice == "3":
            interactive_test()
        elif choice == "4":
            print("👋 Goodbye!")
            sys.exit(0)
        else:
            print("❌ Invalid choice")
    
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted. Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
