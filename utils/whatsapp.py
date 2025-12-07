import requests
import time
from config import ACCESS_TOKEN, PHONE_NUMBER_ID


def format_phone_number(number: str) -> str:
    """Format phone number to WhatsApp standard (remove spaces, dashes, etc.)"""
    # Remove all non-digit characters except '+'
    cleaned = ''.join(c for c in str(number) if c.isdigit() or c == '+')
    
    # Ensure it starts with country code
    if not cleaned.startswith('+'):
        # Add '+' if missing (adjust default country code as needed)
        cleaned = '+' + cleaned
    
    return cleaned


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


def send_template(number: str, template_name: str, params: list, lang="en", retry=True):
    """Send a WhatsApp template message"""
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    
    # Format phone number
    formatted_number = format_phone_number(number)

    template_obj = {
        "name": template_name,
        "language": {"code": lang}
    }

    if params:
        template_obj["components"] = [{
            "type": "body",
            "parameters": [{"type": "text", "text": str(p)} for p in params]
        }]

    payload = {
        "messaging_product": "whatsapp",
        "to": formatted_number,
        "type": "template",
        "template": template_obj
    }

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        
        # Retry once on rate limit (error code 80007)
        if retry and resp.status_code == 429:
            time.sleep(2)
            return send_template(number, template_name, params, lang, retry=False)
        
        return resp.status_code, resp.json()
    
    except requests.exceptions.RequestException as e:
        return 500, {"error": str(e), "type": "request_exception"}


def send_text(number: str, message: str, retry=True):
    """Send a plain text WhatsApp message"""
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    
    # Format phone number
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
        
        # Retry once on rate limit
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


def add_delay_between_messages(delay_seconds=1):
    """Add delay to avoid rate limiting"""
    time.sleep(delay_seconds)