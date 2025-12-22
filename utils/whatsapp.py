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


def create_template(waba_id, template_data, image_file=None):
    """Create a new WhatsApp message template"""
    url = f"https://graph.facebook.com/v20.0/{waba_id}/message_templates"
    
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    components = []
    
    # Header component
    if template_data.get('header_type') == 'TEXT' and template_data.get('header_text'):
        header_text = template_data['header_text'].strip()
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
        image_url = template_data.get('header_image_url', '').strip()
        if image_url:
            if not image_url.startswith('http://') and not image_url.startswith('https://'):
                return 400, {"error": {"message": "Image URL must start with http:// or https://"}}
            
            components.append({
                "type": "HEADER",
                "format": "IMAGE",
                "example": {
                    "header_handle": [image_url]
                }
            })
    
    # Body component (required)
    body_text = template_data['body_text'].strip()
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
    footer_text = template_data.get('footer_text', '').strip()
    if footer_text:
        components.append({
            "type": "FOOTER",
            "text": footer_text
        })
    
    # Buttons component (optional)
    buttons = []
    for i in range(1, 4):
        button_type = template_data.get(f'button_type_{i}')
        button_text = template_data.get(f'button_text_{i}', '').strip()
        button_value = template_data.get(f'button_value_{i}', '').strip()
        
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
    
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        return resp.status_code, resp.json()
    except requests.exceptions.RequestException as e:
        return 500, {"error": {"message": str(e)}, "type": "request_exception"}