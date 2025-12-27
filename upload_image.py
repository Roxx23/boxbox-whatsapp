"""
Quick Image Upload Tool for WhatsApp Templates

Uploads an image to WhatsApp and returns the media ID.
Use this media ID when sending templates with IMAGE headers.
"""

import sys
import os
import requests
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

def upload_image(image_path):
    """
    Upload image to WhatsApp and return media ID
    
    Args:
        image_path: Path to image file (JPEG or PNG, max 5MB)
    
    Returns:
        str: Media ID if successful, None if failed
    """
    
    # Validate file exists
    if not os.path.exists(image_path):
        print(f"❌ File not found: {image_path}")
        return None
    
    # Check file size (5MB limit)
    file_size = os.path.getsize(image_path)
    if file_size > 5 * 1024 * 1024:
        print(f"❌ File too large: {file_size / (1024*1024):.2f}MB (max 5MB)")
        return None
    
    # Determine content type
    ext = image_path.lower().split('.')[-1]
    if ext == 'jpg' or ext == 'jpeg':
        content_type = 'image/jpeg'
    elif ext == 'png':
        content_type = 'image/png'
    else:
        print(f"❌ Unsupported format: {ext} (use JPEG or PNG)")
        return None
    
    print(f"📤 Uploading image...")
    print(f"   File: {image_path}")
    print(f"   Size: {file_size / 1024:.2f} KB")
    print(f"   Type: {content_type}")
    
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/media"
    
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }
    
    try:
        with open(image_path, 'rb') as img_file:
            files = {
                'file': (os.path.basename(image_path), img_file, content_type)
            }
            
            data = {
                'messaging_product': 'whatsapp'
            }
            
            response = requests.post(url, headers=headers, files=files, data=data, timeout=30)
            
            print(f"\n📊 Response Status: {response.status_code}")
            
            if response.status_code in [200, 201]:
                response_data = response.json()
                media_id = response_data.get('id')
                
                print(f"✅ SUCCESS! Image uploaded")
                print(f"\n📋 MEDIA ID:")
                print(f"   {media_id}")
                print(f"\n💾 Save this ID for use in your templates!")
                print(f"\n📝 Usage:")
                print(f"   send_template(..., header_media_id='{media_id}')")
                
                return media_id
            else:
                error_data = response.json()
                print(f"❌ Upload failed")
                print(f"   Error: {error_data}")
                return None
    
    except FileNotFoundError:
        print(f"❌ File not found: {image_path}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def list_recent_media():
    """List recently uploaded media (if API supports it)"""
    print("\n📁 Note: WhatsApp doesn't provide an API to list uploaded media.")
    print("   You need to save media IDs when you upload them.")
    print("   Media IDs typically expire after 30 days.")


def validate_credentials():
    """Check if credentials are configured"""
    if not ACCESS_TOKEN:
        print("❌ ERROR: WHATSAPP_ACCESS_TOKEN not found in .env file")
        return False
    
    if not PHONE_NUMBER_ID:
        print("❌ ERROR: WHATSAPP_PHONE_NUMBER_ID not found in .env file")
        return False
    
    print("✅ Credentials found")
    return True


if __name__ == "__main__":
    print("\n" + "="*60)
    print("🖼️  WhatsApp Image Upload Tool")
    print("="*60)
    
    # Validate credentials
    if not validate_credentials():
        print("\nPlease add the required variables to your .env file:")
        print("  WHATSAPP_ACCESS_TOKEN=your_token_here")
        print("  WHATSAPP_PHONE_NUMBER_ID=your_phone_id_here")
        sys.exit(1)
    
    print("\nOptions:")
    print("1. Upload new image")
    print("2. View usage help")
    print("0. Exit")
    
    try:
        choice = input("\nSelect option (0-2): ").strip()
        
        if choice == "1":
            # Get image path
            if len(sys.argv) > 1:
                image_path = sys.argv[1]
            else:
                image_path = input("\n📁 Enter image file path: ").strip()
                # Remove quotes if present
                image_path = image_path.strip('"').strip("'")
            
            if not image_path:
                print("❌ Image path is required")
                sys.exit(1)
            
            # Upload
            media_id = upload_image(image_path)
            
            if media_id:
                print("\n" + "="*60)
                print("✅ UPLOAD COMPLETE")
                print("="*60)
                
                # Offer to save to file
                save = input("\n💾 Save media ID to file? (y/n): ").strip().lower()
                if save == 'y':
                    filename = "media_ids.txt"
                    with open(filename, 'a') as f:
                        f.write(f"{image_path} → {media_id}\n")
                    print(f"✅ Saved to {filename}")
        
        elif choice == "2":
            print("\n" + "="*60)
            print("📖 USAGE GUIDE")
            print("="*60)
            print("\n1. Run this script:")
            print("   python upload_image.py")
            print("\n2. Or provide image path as argument:")
            print("   python upload_image.py path/to/image.jpg")
            print("\n3. Copy the returned media ID")
            print("\n4. Use in send_template:")
            print("   send_template(")
            print("       number='+919702760931',")
            print("       template_name='new_year_2025_campaign',")
            print("       params=['Ayush'],")
            print("       header_media_id='YOUR_MEDIA_ID_HERE',")
            print("       button_params={'copy_code': 'ITS2026BRO'}")
            print("   )")
            print("\n5. Media IDs are valid for ~30 days")
            print("   You can reuse the same ID for multiple messages")
            
        elif choice == "0":
            print("👋 Goodbye!")
        else:
            print("❌ Invalid choice")
    
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted. Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*60)
