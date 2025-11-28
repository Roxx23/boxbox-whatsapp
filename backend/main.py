from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, UploadFile, Form
import pandas as pd
import requests
import io

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all origins for now
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WHATSAPP_TOKEN = "EAAQmkD88FCUBQNVysPScioo4u1HWR6YkWQemZAGFAh2oEp3afsKm0OZAjmIjwxWnRNENV77rWIZAXWuUYZCjknofpn5c5PypQyoetgtZAJ0OWDHgsbG7zUmgvcwC3vMtZCZAZCoZCbuhkRO33iGp1UZCbinYsLuT8pG7ie47GVP3LaqVfrjQ3LjPyvEUVJWwMoj7ZA2AoIZA3tsK7Ufsm1qZCH7iOik6vdcSRnbZAYkdLHU1wlrNpROWOS2NTELDQuqYYb4PC2WwZAAHgzQ5oFGXg4m9f6GvRwvMyhbzOChK9CyjkgZD"
PHONE_NUMBER_ID = "945931081925931"

@app.post("/upload_excel/") 
async def upload_excel(file: UploadFile):
    content = await file.read()
    df = pd.read_excel(io.BytesIO(content))
    return {"rows": df.to_dict(orient="records")}

@app.post("/send_test/")
async def send_test(number: str = Form(...)):
    payload = {
        "messaging_product": "whatsapp",
        "to": number,
        "type": "text",
        "text": {
            "body": "Hello, this is a test message!"
        }
    }

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    r = requests.post(url, json=payload, headers=headers)

    return {
        "status": r.status_code,
        "response": r.json()
    }

@app.post("/send_bulk_message/")
async def send_bulk_message(message: str = Form(...), numbers: str = Form(...)):
    numbers_list = numbers.split(",")
    results = []

    for number in numbers_list:
        payload = {
            "messaging_product": "whatsapp",
            "to": number,
            "type": "template",
            "template": {
                "name": "boxbox_20_off",        # your template name
                "language": { "code": "en" },   # your template language
                "components": [
                    {
                        "type": "header",
                        "parameters": [
                            {
                                "type": "text",
                                "text": "Abhi Testing"   # EXACT header text
                            }
                        ]
                    },
                    {
                        "type": "body",
                        "parameters": []  # no variables
                    }
                ]
            }
        }

        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }

        url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
        r = requests.post(url, json=payload, headers=headers)

        try:
            resp_json = r.json()
        except:
            resp_json = {"error": "Unable to parse response"}

        print("RESPONSE FOR", number, ":", resp_json)
        results.append({
            "number": number,
            "status": r.status_code,
            "response": resp_json
        })
    

    return {"sent": results}
