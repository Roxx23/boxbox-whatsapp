import requests
from config import ACCESS_TOKEN, PHONE_NUMBER_ID


def get_templates(waba_id):
    url = f"https://graph.facebook.com/v20.0/{waba_id}/message_templates"
    params = {"access_token": ACCESS_TOKEN}
    resp = requests.get(url, params=params)
    return resp.json().get("data", [])


def send_template(number: str, template_name: str, params: list, lang="en"):
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"

    template_obj = {
        "name": template_name,
        "language": {"code": lang}
    }

    if params:
        template_obj["components"] = [{
            "type": "body",
            "parameters": [{"type": "text", "text": p} for p in params]
        }]

    payload = {
        "messaging_product": "whatsapp",
        "to": number,
        "type": "template",
        "template": template_obj
    }

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    resp = requests.post(url, json=payload, headers=headers)
    return resp.status_code, resp.json()


def send_text(number: str, message: str):
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "to": number,
        "type": "text",
        "text": {"body": message},
    }

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    resp = requests.post(url, json=payload, headers=headers)

    try:
        return resp.status_code, resp.json()
    except:
        return resp.status_code, {"raw": resp.text}
