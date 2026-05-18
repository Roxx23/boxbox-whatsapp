import requests
import time
import re
import os
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WABA_ID = os.getenv("WABA_ID")
DEFAULT_COUNTRY_CODE = os.getenv("DEFAULT_COUNTRY_CODE", "91")


def format_phone_number(number: str) -> str:
    """
    Format phone number for WhatsApp Cloud API (digits only, no '+')
    Converts local format (starting with 0) to international format
    
    Examples:
        - +911234567890 -> 911234567890
        - 911234567890 -> 911234567890
        - 01234567890 -> 911234567890 (adds country code, removes leading 0)
        - 1234567890 -> 911234567890 (adds country code if missing)
    """
    # Extract only digits
    digits = ''.join(c for c in str(number) if c.isdigit())
    
    if not digits:
        return digits
    
    # If starts with 0, assume local format - remove 0 and add country code
    if digits.startswith('0'):
        digits = DEFAULT_COUNTRY_CODE + digits[1:]
    
    # If number is too short (less than 10 digits), assume missing country code
    # This handles cases like "1234567890" -> add country code
    elif len(digits) == 10:
        digits = DEFAULT_COUNTRY_CODE + digits
    
    return digits


def get_templates(waba_id):
    """Fetch all WhatsApp message templates (all statuses)"""
    url = f"https://graph.facebook.com/v20.0/{waba_id}/message_templates"
    params = {"access_token": ACCESS_TOKEN, "limit": 100}

    all_templates = []
    try:
        while url:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            all_templates.extend(data.get("data", []))
            url = data.get("paging", {}).get("next")
            params = {}  # next URL already has all params
    except requests.exceptions.RequestException as e:
        print(f"Error fetching templates: {e}")
    return all_templates


def delete_template(waba_id, template_name):
    """Delete a WhatsApp message template by name"""
    url = f"https://graph.facebook.com/v20.0/{waba_id}/message_templates"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    try:
        resp = requests.delete(url, headers=headers, params={"name": template_name}, timeout=10)
        return resp.status_code, resp.json()
    except requests.exceptions.RequestException as e:
        return 500, {"error": {"message": str(e)}}


def send_template(number, template_name, params, lang="en_US", header_media_id=None, button_params=None):
    """Send a WhatsApp template message
    
    Args:
        number: Phone number to send to
        template_name: Name of the template
        params: Body text parameters
        lang: Language code (default: en_US)
        header_media_id: Optional media ID for image header
        button_params: Optional dict with button parameters, e.g.:
            {"copy_code": "SAVE20"} for coupon code button
            {"url_index_0": "param1"} for dynamic URL button parameters
            Or specify index explicitly:
            {"copy_code": "SAVE20", "copy_code_index": 1}
    """
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
    
    # BUTTON PARAMETERS (for copy_code, dynamic URLs, etc.)
    if button_params:
        button_components = []
        
        # Debug: Print what we received
        print(f"🔍 Button params received: {button_params}")
        
        # Handle copy_code button (utility button for coupons)
        if "copy_code" in button_params:
            # Allow explicit index specification, otherwise try to detect from template
            if "copy_code_index" in button_params:
                index = str(button_params["copy_code_index"])
            else:
                # Try to auto-detect button index from template
                index = "0"  # Default assumption
                
                # If we have WABA_ID, try to detect correct index
                if WABA_ID:
                    try:
                        templates = get_templates(WABA_ID)
                        template = next((t for t in templates if t["name"] == template_name), None)
                        
                        if template:
                            buttons_comp = next((c for c in template["components"] if c["type"] == "BUTTONS"), None)
                            if buttons_comp and "buttons" in buttons_comp:
                                # Find COPY_CODE button index
                                for idx, btn in enumerate(buttons_comp["buttons"]):
                                    if btn.get("type") == "COPY_CODE":
                                        index = str(idx)
                                        print(f"🔍 Auto-detected COPY_CODE button at index {index}")
                                        break
                    except Exception as e:
                        print(f"⚠️  Could not auto-detect button index: {e}")
                        pass
            
            print(f"📋 Adding COPY_CODE button: index={index}, code={button_params['copy_code']}")
            button_components.append({
                "type": "button",
                "sub_type": "copy_code",
                "index": index,
                "parameters": [{
                    "type": "coupon_code",
                    "coupon_code": str(button_params["copy_code"])
                }]
            })
        else:
            print("⚠️  No 'copy_code' found in button_params!")
        
        # Handle dynamic URL parameters (for URL buttons with variables)
        for key, value in button_params.items():
            if key.startswith("url_index_"):
                index = key.split("_")[-1]
                button_components.append({
                    "type": "button",
                    "sub_type": "url",
                    "index": index,
                    "parameters": [{
                        "type": "text",
                        "text": str(value)
                    }]
                })
        
        components.extend(button_components)
    else:
        print("⚠️  button_params is None or empty!")

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


def upload_image_for_template(image_file):
    """
    Upload an image for WhatsApp template header using the Resumable Upload API.
    Returns (handle, error_message). Handle starts with 'h:' and is used in header_handle.
    """
    image_file.seek(0, 2)
    file_size = image_file.tell()
    image_file.seek(0)

    file_name = image_file.filename
    mime_type = image_file.content_type or 'image/jpeg'

    # Step 1: Create upload session
    session_resp = requests.post(
        "https://graph.facebook.com/v20.0/app/uploads",
        params={
            "file_name": file_name,
            "file_length": file_size,
            "file_type": mime_type,
            "access_token": ACCESS_TOKEN,
        },
        timeout=15,
    )
    if session_resp.status_code not in [200, 201]:
        return None, f"Failed to create upload session: {session_resp.text}"

    session_id = session_resp.json().get("id")
    if not session_id:
        return None, "No session ID returned from upload session"

    # Step 2: Upload the binary data
    file_data = image_file.read()
    upload_resp = requests.post(
        f"https://graph.facebook.com/v20.0/{session_id}",
        headers={
            "Authorization": f"OAuth {ACCESS_TOKEN}",
            "file_offset": "0",
            "Content-Type": mime_type,
        },
        data=file_data,
        timeout=60,
    )
    if upload_resp.status_code not in [200, 201]:
        return None, f"Upload failed: {upload_resp.text}"

    handle = upload_resp.json().get("h")
    if not handle:
        return None, f"No handle returned: {upload_resp.text}"

    return handle, None


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
        if not (image_file and image_file.filename):
            return 400, {"error": {"message": "Please select an image file for the image header."}}

        image_file.seek(0, 2)
        file_size = image_file.tell()
        image_file.seek(0)

        if file_size == 0:
            return 400, {"error": {"message": "Image file is empty."}}
        if file_size > 5 * 1024 * 1024:
            return 400, {"error": {"message": "Image too large. Maximum 5 MB."}}

        handle, err = upload_image_for_template(image_file)
        if err:
            return 400, {"error": {"message": f"Image upload failed: {err}"}}

        components.append({
            "type": "HEADER",
            "format": "IMAGE",
            "example": {"header_handle": [handle]},
        })
    
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