import logging
import requests
import time
import re
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

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
    url = f"https://graph.facebook.com/v21.0/{waba_id}/message_templates"
    # Without an explicit fields= param, the Graph API's default field set omits
    # quality_score and rejected_reason -- templates_manager.html already has
    # display code for rejected_reason that was silently dead for exactly this
    # reason. Everything else here is a field some part of the app already reads
    # off a template dict (name/status/category/language/components).
    fields = "id,name,status,category,language,components,quality_score,rejected_reason"
    params = {"access_token": ACCESS_TOKEN, "limit": 100, "fields": fields}

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
        logger.error(f"Error fetching templates: {e}")
    return all_templates


def delete_template(waba_id, template_name):
    """Delete a WhatsApp message template by name"""
    url = f"https://graph.facebook.com/v21.0/{waba_id}/message_templates"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    try:
        resp = requests.delete(url, headers=headers, params={"name": template_name}, timeout=10)
        return resp.status_code, resp.json()
    except requests.exceptions.RequestException as e:
        return 500, {"error": {"message": str(e)}}


def send_template(number, template_name, params, lang="en_US", header_media_id=None, button_params=None,
                   header_param=None, header_media_type="image"):
    """Send a WhatsApp template message

    Args:
        number: Phone number to send to
        template_name: Name of the template
        params: Body text parameters
        lang: Language code (default: en_US)
        header_media_id: Optional media ID for an image/video/document header
        header_media_type: Which kind of media header_media_id is — 'image'
            (default), 'video', or 'document'. Ignored when header_media_id
            isn't set.
        button_params: Optional dict with button parameters, e.g.:
            {"copy_code": "SAVE20"} for coupon code button
            {"url_index_0": "param1"} for dynamic URL button parameters
            Or specify index explicitly:
            {"copy_code": "SAVE20", "copy_code_index": 1}
        header_param: Optional text value for a TEXT header's {{1}} variable.
            Ignored if header_media_id is set (a template header is either
            media (image/video/document) or a text variable, never both).
    """
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"

    formatted_number = format_phone_number(number)

    components = []

    # MEDIA HEADER (image/video/document — WhatsApp's parameter shape is the
    # same for all three, just keyed by the type name)
    if header_media_id:
        components.append({
            "type": "header",
            "parameters": [{
                "type": header_media_type,
                header_media_type: {"id": header_media_id}
            }]
        })
    elif header_param is not None:
        components.append({
            "type": "header",
            "parameters": [{
                "type": "text",
                "text": str(header_param)
            }]
        })

    # BODY PARAMETERS
    if params:
        components.append({
            "type": "body",
            "parameters": [{"type": "text", "text": str(p)} for p in params]
        })
    
    # BUTTON PARAMETERS (for copy_code, dynamic URLs, CATALOG, etc.)
    button_components = []

    # CATALOG buttons take no per-recipient data (no {{n}} in the template,
    # unlike URL/COPY_CODE), so this can't be gated behind `if button_params`
    # like the rest of this section -- it must run even when the caller
    # passed nothing. WhatsApp still requires an explicit components entry
    # (sub_type=CATALOG with an action object, thumbnail_product_retailer_id
    # optional) for the catalog to attach to the send at all.
    if WABA_ID:
        try:
            templates = get_templates(WABA_ID)
            template = next((t for t in templates if t["name"] == template_name), None)
            if template:
                buttons_comp = next((c for c in template["components"] if c["type"] == "BUTTONS"), None)
                if buttons_comp and "buttons" in buttons_comp:
                    for idx, btn in enumerate(buttons_comp["buttons"]):
                        if btn.get("type") == "CATALOG":
                            action = {}
                            thumbnail_id = (button_params or {}).get("catalog_thumbnail_retailer_id")
                            if thumbnail_id:
                                action["thumbnail_product_retailer_id"] = str(thumbnail_id)
                            button_components.append({
                                "type": "button",
                                "sub_type": "CATALOG",
                                "index": str(idx),
                                "parameters": [{"type": "action", "action": action}]
                            })
                            logger.debug(f"Adding CATALOG button at index {idx}")
                            break
        except Exception as e:
            logger.warning(f"Could not check for CATALOG button: {e}")

    if button_params:
        logger.debug(f"Button params: {button_params}")

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
                                        logger.debug(f"Auto-detected COPY_CODE button at index {index}")
                                        break
                    except Exception as e:
                        logger.warning(f"Could not auto-detect button index: {e}")
            
            logger.debug(f"Adding COPY_CODE button: index={index}, code={button_params['copy_code']}")
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
            logger.warning("No 'copy_code' found in button_params")
        
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
        
    if button_components:
        components.extend(button_components)
    else:
        logger.debug("No button components for this template (expected if template has no buttons)")

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

    logger.info(f"Sending template '{template_name}' to {formatted_number} (lang={lang})")
    logger.debug(f"Payload: {payload}")

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        response_data = resp.json()
        
        if resp.status_code in [200, 201]:
            logger.info(f"Template sent OK ({resp.status_code}) to {formatted_number}")
        else:
            logger.warning(f"Template send returned {resp.status_code} for {formatted_number}: {response_data}")
        logger.debug(f"Response: {response_data}")
        
        # Retry on rate limit
        if resp.status_code == 429:
            time.sleep(2)
            return send_template(number, template_name, params, lang, header_media_id, button_params, header_param, header_media_type)
        
        return resp.status_code, response_data
    except requests.exceptions.RequestException as e:
        logger.error(f"Template send request failed for {formatted_number}: {e}")
        return 500, {"error": str(e), "type": "request_exception"}


def send_text(number: str, message: str, retry=True):
    """Send a plain text WhatsApp message"""
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
    
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
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/media"

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
    }

    image_file.seek(0)
    image_bytes = image_file.read()

    # Determine a safe content type — WhatsApp only accepts image/jpeg and image/png
    content_type = image_file.content_type or 'image/jpeg'
    if content_type not in ('image/jpeg', 'image/png'):
        content_type = 'image/jpeg'

    filename = image_file.filename or 'header.jpg'
    logger.info(f"Uploading media: filename={filename}, content_type={content_type}, size={len(image_bytes)} bytes")

    files = {
        'file': (filename, image_bytes, content_type)
    }

    data = {
        'messaging_product': 'whatsapp'
    }

    try:
        resp = requests.post(url, headers=headers, files=files, data=data, timeout=30)

        if resp.status_code in [200, 201]:
            media_id = resp.json().get('id')
            logger.info(f"Media uploaded OK, ID: {media_id}")
            return media_id
        else:
            logger.error(f"Media upload failed ({resp.status_code}): {resp.json()}")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Media upload exception: {e}")
        return None


def upload_media_from_bytes(image_bytes, content_type='image/jpeg', filename='product.jpg'):
    """Upload raw image bytes to WhatsApp media API. Returns media_id or None.
    Used for automation (e.g. product image from Shopify CDN → WhatsApp header)."""
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/media"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    files = {'file': (filename, image_bytes, content_type)}
    data = {'messaging_product': 'whatsapp'}
    try:
        resp = requests.post(url, headers=headers, files=files, data=data, timeout=30)
        if resp.status_code in [200, 201]:
            media_id = resp.json().get('id')
            logger.info(f"Media (bytes) uploaded OK, ID: {media_id}")
            return media_id
        else:
            logger.error(f"Media (bytes) upload failed ({resp.status_code}): {resp.json()}")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Media (bytes) upload exception: {e}")
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
    logger.debug(f"Image saved to: {filepath}")
    
    return filepath


def upload_media_for_template(media_file, default_mime_type='image/jpeg'):
    """
    Upload a file (image, video, or document) for a WhatsApp template header
    using the Resumable Upload API. The API itself is media-type-agnostic --
    the same two-step session+upload flow handles all three, keyed only by the
    mime_type/file_length passed at session-creation time.
    Returns (handle, error_message). Handle starts with 'h:' and is used in header_handle.
    """
    media_file.seek(0, 2)
    file_size = media_file.tell()
    media_file.seek(0)

    file_name = media_file.filename
    mime_type = media_file.content_type or default_mime_type

    # Step 1: Create upload session
    session_resp = requests.post(
        "https://graph.facebook.com/v21.0/app/uploads",
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
    file_data = media_file.read()
    upload_resp = requests.post(
        f"https://graph.facebook.com/v21.0/{session_id}",
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


# WhatsApp's actual per-component limits. Enforced here (not just in the
# create-template form) because the form's client-side checks are trivially
# bypassable by posting to /submit-template directly -- without a server-side
# check, an over-limit template would sail past this app and get rejected by
# Meta with a much less specific error.
_HEADER_TEXT_MAX = 60
_BODY_TEXT_MAX = 1024
_FOOTER_TEXT_MAX = 60
_BUTTON_TEXT_MAX = 25
_TEMPLATE_NAME_RE = re.compile(r'^[a-z0-9_]+$')

# Sample-media size ceilings for a media-header template at creation time.
# Meta's template docs don't state a creation-specific limit separately from
# the general WhatsApp Cloud API media-message limits, so those are what's
# enforced here too: image 5MB (the pre-existing limit), video 16MB,
# document 100MB.
_MEDIA_HEADER_MAX_BYTES = {
    'IMAGE': 5 * 1024 * 1024,
    'VIDEO': 16 * 1024 * 1024,
    'DOCUMENT': 100 * 1024 * 1024,
}
_MEDIA_HEADER_DEFAULT_MIME = {
    'IMAGE': 'image/jpeg',
    'VIDEO': 'video/mp4',
    'DOCUMENT': 'application/pdf',
}


def _validate_body_variable_numbering(body_text):
    """WhatsApp requires {{n}} placeholders to be sequential starting at 1
    (e.g. {{1}},{{2}},{{3}} -- not {{1}},{{3}} skipping {{2}}, and not
    starting at {{2}}). A gap is accepted by this app's own regex-based
    extraction (which just collects whatever numbers appear) but rejected by
    Meta at submission time. Returns an error message, or None if fine."""
    numbers = sorted(set(int(n) for n in re.findall(r'\{\{(\d+)\}\}', body_text)))
    if not numbers:
        return None
    expected = list(range(1, len(numbers) + 1))
    if numbers != expected:
        found_str = ', '.join('{{%d}}' % n for n in numbers)
        expected_str = ', '.join('{{%d}}' % n for n in expected)
        return (
            "Body variables must be sequential starting at {{1}} with no gaps "
            "(found " + found_str + ", expected " + expected_str + ")"
        )
    return None


def create_template(waba_id, template_data, media_file=None):
    """Create a new WhatsApp message template"""

    # Validate credentials
    if not ACCESS_TOKEN or ACCESS_TOKEN == "None":
        return 500, {"error": {"message": "WHATSAPP_ACCESS_TOKEN not configured. Check your .env file."}}

    if not waba_id or waba_id == "None":
        return 500, {"error": {"message": "WABA_ID not configured. Check your .env file."}}

    template_name = (template_data.get('template_name') or '').strip().lower()
    if not template_name or not _TEMPLATE_NAME_RE.match(template_name):
        return 400, {"error": {"message": "Template name must contain only lowercase letters, numbers, and underscores"}}

    url = f"https://graph.facebook.com/v21.0/{waba_id}/message_templates"

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    logger.debug(f"Create template API endpoint: {url} (WABA: {waba_id})")

    components = []

    # Header component
    if template_data.get('header_type') == 'TEXT' and template_data.get('header_text'):
        header_text = template_data.get('header_text') or ''
        header_text = header_text.strip() if header_text else ''
        if header_text:
            if len(header_text) > _HEADER_TEXT_MAX:
                return 400, {"error": {"message": f"Header text must be {_HEADER_TEXT_MAX} characters or fewer (got {len(header_text)})"}}
            header_component = {
                "type": "HEADER",
                "format": "TEXT",
                "text": header_text
            }
            if '{{1}}' in header_text:
                header_component['example'] = {"header_text": ["Sample Value"]}
            components.append(header_component)
    
    elif template_data.get('header_type') in _MEDIA_HEADER_MAX_BYTES:
        media_type = template_data['header_type']
        media_label = media_type.lower()

        if not (media_file and media_file.filename):
            return 400, {"error": {"message": f"Please select a file for the {media_label} header."}}

        media_file.seek(0, 2)
        file_size = media_file.tell()
        media_file.seek(0)

        if file_size == 0:
            return 400, {"error": {"message": f"{media_type.title()} file is empty."}}
        max_bytes = _MEDIA_HEADER_MAX_BYTES[media_type]
        if file_size > max_bytes:
            return 400, {"error": {"message": f"{media_type.title()} too large. Maximum {max_bytes // (1024 * 1024)} MB."}}

        handle, err = upload_media_for_template(media_file, _MEDIA_HEADER_DEFAULT_MIME[media_type])
        if err:
            return 400, {"error": {"message": f"{media_type.title()} upload failed: {err}"}}

        components.append({
            "type": "HEADER",
            "format": media_type,
            "example": {"header_handle": [handle]},
        })

    elif template_data.get('header_type') == 'LOCATION':
        # LOCATION headers need nothing at creation time -- per Meta's docs,
        # "Creation parameters: None". Unlike IMAGE/VIDEO/DOCUMENT there's no
        # sample media to upload; the actual lat/lng/name/address are supplied
        # per-send (same asymmetry already handled on the send side for Flows).
        components.append({
            "type": "HEADER",
            "format": "LOCATION",
        })

    # Body component (required)
    body_text = template_data.get('body_text') or ''
    body_text = body_text.strip() if body_text else ''
    if not body_text:
        return 400, {"error": {"message": "Body text is required"}}
    if len(body_text) > _BODY_TEXT_MAX:
        return 400, {"error": {"message": f"Body text must be {_BODY_TEXT_MAX} characters or fewer (got {len(body_text)})"}}

    numbering_error = _validate_body_variable_numbering(body_text)
    if numbering_error:
        return 400, {"error": {"message": numbering_error}}

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
        if len(footer_text) > _FOOTER_TEXT_MAX:
            return 400, {"error": {"message": f"Footer text must be {_FOOTER_TEXT_MAX} characters or fewer (got {len(footer_text)})"}}
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

        if len(button_text) > _BUTTON_TEXT_MAX:
            return 400, {"error": {"message": f"Button {i} text must be {_BUTTON_TEXT_MAX} characters or fewer (got {len(button_text)})"}}

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
        "name": template_name,
        "language": template_data['language'],
        "category": template_data['category'],
        "components": components
    }
    
    logger.debug(f"Create template payload: {payload}")

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        response_json = resp.json()

        if resp.status_code in [200, 201]:
            logger.info(f"Template '{payload['name']}' submitted for approval ({resp.status_code})")
        else:
            logger.warning(f"Template submission returned {resp.status_code}: {response_json}")
        logger.debug(f"Template create response: {response_json}")
        
        return resp.status_code, response_json
    except requests.exceptions.RequestException as e:
        return 500, {"error": {"message": str(e)}, "type": "request_exception"}