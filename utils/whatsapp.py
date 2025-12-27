import requests
import time
import re
from config import ACCESS_TOKEN, PHONE_NUMBER_ID


def format_phone_number(number: str) -> str:
    """WhatsApp Cloud API requires digits only, no '+'"""
    digits = ''.join(c for c in str(number) if c.isdigit())
    return digits


def get_templates(waba_id):
    """Fetch all approved WhatsApp message templates"""
    url = f"https://graph.facebook.com/v20.0/{waba_id}/message_templates"
    params = {"access_token": ACCESS_TOKEN}
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json().get("data", [])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching templates: {e}")
        return []


def send_template(number, template_name, params, lang="en_US", header_media_id=None):
    """Send a WhatsApp template message"""
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"

    formatted_number = format_phone_number(number)

    components = []

    # IMAGE HEADER (if provided)
    if header_media_id:
        components.append({
            "type": "header",
            "parameters": [{
                "type": "image",
                "image": {"id": header_media_id}
            }]
        })

    # BODY PARAMETERS
    if params:
        components.append({
            "type": "body",
            "parameters": [{"type": "text", "text": str(p)} for p in params]
        })

    payload = {
        "messaging_product": "whatsapp",
        "to": formatted_number,
        "type": "template",
        "template": {
            "name": template_name.lower(),
            "language": {"code": lang},
            "components": components
        }
    }

    # DEBUG PRINTS
    print("=" * 50)
    print(f"📞 Sending to: {formatted_number}")
    print(f"📝 Template: {template_name}")
    print(f"🌍 Language: {lang}")
    print(f"📦 Payload: {payload}")
    print("=" * 50)

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        response_data = resp.json()
        
        print(f"✅ Status: {resp.status_code}")
        print(f"📨 Response: {response_data}")
        print("=" * 50)
        
        # Retry on rate limit
        if resp.status_code == 429:
            time.sleep(2)
            return send_template(number, template_name, params, lang, header_media_id)
        
        return resp.status_code, response_data
    except requests.exceptions.RequestException as e:
        print(f"❌ Error: {e}")
        return 500, {"error": str(e), "type": "request_exception"}


def send_text(number: str, message: str, retry=True):
    """Send a plain text WhatsApp message"""
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    
    formatted_number = format_phone_number(number)

    payload = {
        "messaging_product": "whatsapp",
        "to": formatted_number,
        "type": "text",
        "text": {"body": message},
    }

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        
        if retry and resp.status_code == 429:
            time.sleep(2)
            return send_text(number, message, retry=False)
        
        return resp.status_code, resp.json()
    
    except requests.exceptions.Timeout:
        return 408, {"error": "Request timeout", "type": "timeout"}
    except requests.exceptions.RequestException as e:
        return 500, {"error": str(e), "type": "request_exception"}
    except Exception as e:
        return 500, {"error": str(e), "type": "unknown"}


def upload_media(image_file):
    """Upload media to WhatsApp and get media ID"""
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/media"
    
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
    }
    
    image_file.seek(0)
    
    files = {
        'file': (image_file.filename, image_file.stream, image_file.content_type)
    }
    
    data = {
        'messaging_product': 'whatsapp'
    }
    
    try:
        resp = requests.post(url, headers=headers, files=files, data=data, timeout=30)
        
        if resp.status_code in [200, 201]:
            media_id = resp.json().get('id')
            print(f"✅ Media uploaded successfully. ID: {media_id}")
            return media_id
        else:
            print(f"❌ Media upload error: {resp.json()}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Media upload exception: {e}")
        return None


def save_uploaded_image(image_file):
    """
    Save uploaded image temporarily and return file path
    This is for local hosting/serving of template images
    """
    import os
    from werkzeug.utils import secure_filename
    
    # Create uploads directory if it doesn't exist
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    
    # Generate secure filename
    filename = secure_filename(image_file.filename)
    timestamp = str(int(time.time()))
    unique_filename = f"{timestamp}_{filename}"
    filepath = os.path.join(upload_dir, unique_filename)
    
    # Save file
    image_file.save(filepath)
    print(f"✅ Image saved to: {filepath}")
    
    return filepath


def upload_media_for_template(image_file):
    """
    For WhatsApp template creation with IMAGE header:
    We need to provide a publicly accessible URL as an example.
    
    Option 1: Upload to WhatsApp media and use that URL (not always public)
    Option 2: Use a publicly hosted image URL (recommended)
    Option 3: Save locally and provide public URL if you have a domain
    
    This function uploads to WhatsApp and returns whatever identifier we can use.
    """
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/media"
    
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
    }
    
    # Reset file pointer to beginning
    image_file.seek(0)
    
    # Read file content
    file_content = image_file.read()
    image_file.seek(0)  # Reset again for potential reuse
    
    files = {
        'file': (image_file.filename, file_content, image_file.content_type)
    }
    
    data = {
        'messaging_product': 'whatsapp'
    }
    
    try:
        # Upload the file
        print(f"📤 Uploading to WhatsApp: {image_file.filename} ({len(file_content)} bytes)")
        resp = requests.post(url, headers=headers, files=files, data=data, timeout=30)
        
        print(f"Upload response status: {resp.status_code}")
        print(f"Upload response: {resp.text}")
        
        if resp.status_code not in [200, 201]:
            error_data = resp.json() if resp.text else {}
            error_msg = error_data.get('error', {}).get('message', 'Unknown error')
            print(f"❌ Media upload error: {error_msg}")
            return None
        
        response_data = resp.json()
        media_id = response_data.get('id')
        
        if media_id:
            print(f"✅ Media uploaded. ID: {media_id}")
            # For templates, we'll use a placeholder URL or the media ID
            # WhatsApp will accept the ID as handle in some cases
            return media_id
        else:
            print(f"❌ No media ID in response: {response_data}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Media upload exception: {e}")
        import traceback
        traceback.print_exc()
        return None


def create_template(waba_id, template_data, image_file=None):
    """Create a new WhatsApp message template"""
    
    # Validate credentials
    if not ACCESS_TOKEN or ACCESS_TOKEN == "None":
        return 500, {"error": {"message": "WHATSAPP_ACCESS_TOKEN not configured. Check your .env file."}}
    
    if not waba_id or waba_id == "None":
        return 500, {"error": {"message": "WABA_ID not configured. Check your .env file."}}
    
    url = f"https://graph.facebook.com/v21.0/{waba_id}/message_templates"
    
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    print(f"🌐 API Endpoint: {url}")
    print(f"🔑 Using WABA ID: {waba_id}")
    print(f"🔑 Access Token (first 20 chars): {ACCESS_TOKEN[:20] if ACCESS_TOKEN else 'MISSING'}...")
    
    components = []
    
    # Header component
    if template_data.get('header_type') == 'TEXT' and template_data.get('header_text'):
        header_text = template_data.get('header_text') or ''
        header_text = header_text.strip() if header_text else ''
        if header_text:
            header_component = {
                "type": "HEADER",
                "format": "TEXT",
                "text": header_text
            }
            if '{{1}}' in header_text:
                header_component['example'] = {"header_text": ["Sample Value"]}
            components.append(header_component)
    
    elif template_data.get('header_type') == 'IMAGE':
        image_handle = None
        
        # Priority 1: Check for image URL (more reliable for templates)
        image_url = template_data.get('header_image_url') or ''
        image_url = image_url.strip() if image_url else ''
        
        if image_url:
            print(f"🔗 Using provided image URL: {image_url}")
            print(f"🔍 URL type: {type(image_url)}")
            print(f"🔍 URL length: {len(image_url)}")
            print(f"🔍 URL repr: {repr(image_url)}")
            print(f"🔍 First 10 chars: {repr(image_url[:10])}")
            print(f"🔍 Starts with http://: {image_url.startswith('http://')}")
            print(f"🔍 Starts with https://: {image_url.startswith('https://')}")
            
            # Validate URL format
            if not image_url.startswith('http://') and not image_url.startswith('https://'):
                print(f"❌ VALIDATION FAILED - URL does not start with http:// or https://")
                print(f"   URL bytes: {image_url.encode('utf-8')[:50]}")
                return 400, {"error": {"message": "Image URL must start with http:// or https://"}}
            
            # Check if it's a direct image link
            if 'imgur.com/a/' in image_url or 'imgur.com/gallery/' in image_url:
                return 400, {"error": {"message": "Please use a direct image link, not an Imgur album/gallery URL. Right-click the image and copy image address, or add .jpg/.png to the end (e.g., https://i.imgur.com/xxxxx.jpg)"}}
            
            # Check if URL has special characters that might cause issues
            if '(' in image_url or ')' in image_url:
                print(f"⚠️ Warning: URL contains parentheses which may cause issues with some APIs")
            
            # Warn about other potential non-direct links
            if not any(image_url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                print(f"⚠️ Warning: URL doesn't end with image extension. This might not be a direct image link.")
            
            image_handle = image_url
        
        # Priority 2: Try image file upload if no URL provided
        elif image_file and image_file.filename:
            print(f"📤 Uploading image for template: {image_file.filename}")
            
            # Save file size check
            image_file.seek(0, 2)  # Seek to end
            file_size = image_file.tell()
            image_file.seek(0)  # Reset to beginning
            
            print(f"📊 File size: {file_size} bytes ({file_size / 1024:.2f} KB)")
            
            if file_size > 5 * 1024 * 1024:  # 5MB limit
                return 400, {"error": {"message": "Image file too large. Maximum 5MB allowed."}}
            
            if file_size == 0:
                return 400, {"error": {"message": "Image file is empty. Please select a valid image."}}
            
            image_handle = upload_media_for_template(image_file)
            
            if not image_handle:
                return 400, {"error": {"message": "Failed to upload image. Please try providing an image URL instead."}}
            
            print(f"✅ Image uploaded with handle: {image_handle}")
        
        # No image provided
        else:
            print("⚠️ No image file or URL provided for IMAGE header")
            return 400, {"error": {"message": "Please provide either an image file or image URL for IMAGE header. For best results, use a publicly accessible HTTPS URL."}}
        
        # IMAGE header format for WhatsApp template creation:
        # The example MUST be a publicly accessible HTTPS URL, not a media ID
        # If we have a media ID from upload, we cannot use it directly for template creation
        
        # Validate that we have a proper URL, not just a media ID
        if image_handle and not image_handle.startswith('http'):
            # If it's a media ID (numeric), we need to inform the user
            print(f"⚠️ Warning: Got media ID '{image_handle}' but template creation needs a URL")
            return 400, {"error": {"message": "Template creation requires a publicly accessible image URL. The uploaded file returned a media ID which cannot be used for template creation. Please provide a direct HTTPS URL instead (e.g., https://i.imgur.com/xxxxx.jpg)"}}
        
        # URL-encode special characters in the URL
        # NOTE: Some APIs don't like encoded URLs, let's try without encoding first
        original_handle = image_handle
        
        from urllib.parse import quote
        # Only encode the path part, not the protocol and domain
        if '(' in image_handle or ')' in image_handle or ' ' in image_handle:
            print(f"⚠️ URL contains special characters: {image_handle}")
            print(f"   Suggestion: Consider renaming the file to remove special characters")
            # DON'T encode for now - WhatsApp might prefer the original URL
            # Split URL into parts
            # parts = image_handle.split('/', 3)
            # if len(parts) >= 4:
            #     encoded_path = quote(parts[3], safe='/:.-_~')
            #     image_handle_encoded = f"{parts[0]}//{parts[2]}/{encoded_path}"
            #     print(f"   Original: {image_handle}")
            #     print(f"   Encoded:  {image_handle_encoded}")
            #     image_handle = image_handle_encoded
        
        # WhatsApp Cloud API format for IMAGE header in templates
        # The correct field is "header_url" (not header_text or header_handle)
        header_component = {
            "type": "HEADER",
            "format": "IMAGE",
            "example": {
                "header_url": [
                    image_handle
                ]
            }
        }
        
        components.append(header_component)
        
        print(f"✅ IMAGE header component structure:")
        print(f"   type: HEADER")
        print(f"   format: IMAGE")
        print(f"   example.header_url[0]: '{image_handle}'")
    
    # Body component (required)
    body_text = template_data.get('body_text') or ''
    body_text = body_text.strip() if body_text else ''
    if not body_text:
        return 400, {"error": {"message": "Body text is required"}}
    
    body_component = {
        "type": "BODY",
        "text": body_text
    }
    
    variables = re.findall(r'\{\{(\d+)\}\}', body_text)
    if variables:
        example_values = [f"Sample{i}" for i in range(1, len(variables) + 1)]
        body_component['example'] = {"body_text": [example_values]}
    
    components.append(body_component)
    
    # Footer component (optional)
    footer_text = template_data.get('footer_text', '') or ''
    footer_text = footer_text.strip() if footer_text else ''
    if footer_text:
        components.append({
            "type": "FOOTER",
            "text": footer_text
        })
    
    # Buttons component (optional)
    buttons = []
    for i in range(1, 4):
        button_type = template_data.get(f'button_type_{i}')
        button_text = template_data.get(f'button_text_{i}') or ''
        button_value = template_data.get(f'button_value_{i}') or ''
        
        # Safely strip strings
        button_text = button_text.strip() if button_text else ''
        button_value = button_value.strip() if button_value else ''
        
        if not button_type or not button_text or not button_value:
            continue
        
        if button_type == 'URL':
            if not button_value.startswith('http://') and not button_value.startswith('https://'):
                return 400, {"error": {"message": f"Button {i} URL must start with http:// or https://"}}
            
            buttons.append({
                "type": "URL",
                "text": button_text,
                "url": button_value
            })
        elif button_type == 'PHONE_NUMBER':
            if not button_value.startswith('+'):
                return 400, {"error": {"message": f"Button {i} phone must start with + and country code"}}
            
            buttons.append({
                "type": "PHONE_NUMBER",
                "text": button_text,
                "phone_number": button_value
            })
    
    if buttons:
        components.append({
            "type": "BUTTONS",
            "buttons": buttons
        })
    
    payload = {
        "name": template_data['template_name'].strip().lower(),
        "language": template_data['language'],
        "category": template_data['category'],
        "components": components
    }
    
    print("=" * 60)
    print("📦 Template Payload (sending to WhatsApp):")
    import json
    print(json.dumps(payload, indent=2))
    print("=" * 60)
    
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        response_json = resp.json()
        
        print("=" * 60)
        print(f"📥 Response Status: {resp.status_code}")
        print(f"📥 Response Body:")
        print(json.dumps(response_json, indent=2))
        print("=" * 60)
        
        return resp.status_code, response_json
    except requests.exceptions.RequestException as e:
        return 500, {"error": {"message": str(e)}, "type": "request_exception"}