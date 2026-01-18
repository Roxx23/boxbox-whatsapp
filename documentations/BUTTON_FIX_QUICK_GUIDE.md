# Quick Fix for Copy Code Button Error

## Your Current Error
```
ERROR: (#131008) Required parameter is missing
buttons: Button at index 1 of type copy_code requires a non-empty parameter coupon_code
```

## Immediate Solution

Your template has:
1. Button 1: **Utility button (COPY_CODE)** - requires `coupon_code` parameter
2. Button 2: **Call to Action button (URL)** - works fine

### Step 1: Prepare Your CSV

Add a column for the coupon code:

```csv
Name,Phone,CouponCode
John Doe,+919156143465,SAVE20
Jane Smith,+919876543210,WELCOME10
```

### Step 2: Manual API Test (Direct Fix)

You can test sending this template directly using Python:

```python
from utils.whatsapp import send_template

# Your template details
phone = "+919156143465"
template_name = "your_template_name"  # Replace with actual name
params = []  # Body parameters if any
language = "en_US"

# Add button parameters
button_params = {
    "copy_code": "SAVE20"  # Your coupon code
}

# Send
status, response = send_template(
    phone,
    template_name,
    params,
    language,
    button_params=button_params
)

print(f"Status: {status}")
print(f"Response: {response}")
```

### Step 3: Quick Test Script

Create a file `test_button_template.py`:

```python
import sys
from utils.whatsapp import send_template

# Configure
PHONE = "+919156143465"  # Your test number
TEMPLATE_NAME = "your_template_name"  # Replace with actual template name
COUPON_CODE = "SAVE20"

# Test send
print(f"🚀 Testing template with coupon code button...")
print(f"   Template: {TEMPLATE_NAME}")
print(f"   Phone: {PHONE}")
print(f"   Coupon: {COUPON_CODE}")

status, response = send_template(
    number=PHONE,
    template_name=TEMPLATE_NAME,
    params=[],  # Add body parameters if needed
    lang="en_US",
    button_params={"copy_code": COUPON_CODE}
)

if status == 200:
    print(f"✅ SUCCESS! Message sent")
    print(f"Response: {response}")
else:
    print(f"❌ FAILED with status {status}")
    print(f"Error: {response}")
```

Run it:
```bash
python test_button_template.py
```

### Step 4: Find Your Template Name

If you don't know your template name:

```python
from utils.whatsapp import get_templates
from config import WABA_ID

templates = get_templates(WABA_ID)

print("Your templates with buttons:")
for t in templates:
    # Check if has buttons
    buttons_component = next((c for c in t["components"] if c["type"] == "BUTTONS"), None)
    if buttons_component:
        print(f"\n📋 Template: {t['name']}")
        print(f"   Language: {t.get('language', 'N/A')}")
        print(f"   Buttons:")
        for idx, btn in enumerate(buttons_component["buttons"]):
            print(f"      {idx+1}. {btn.get('type')} - {btn.get('text')}")
```

## What Changed in the Code

### Before (Error):
```python
# Only sent header and body parameters
send_template(phone, template_name, params, lang, header_media_id)
```

### After (Fixed):
```python
# Now includes button parameters
send_template(
    phone, 
    template_name, 
    params, 
    lang, 
    header_media_id,
    button_params={"copy_code": "SAVE20"}
)
```

## WhatsApp API Payload Difference

### Before (Missing button params):
```json
{
  "template": {
    "components": [
      {"type": "body", "parameters": [...]}
    ]
  }
}
```

### After (Complete):
```json
{
  "template": {
    "components": [
      {"type": "body", "parameters": [...]},
      {
        "type": "button",
        "sub_type": "copy_code",
        "index": "0",
        "parameters": [{
          "type": "coupon_code",
          "coupon_code": "SAVE20"
        }]
      }
    ]
  }
}
```

## Frontend Integration (Coming Soon)

The UI needs to be updated to:
1. Detect templates with copy_code buttons
2. Show a field: "Coupon Code Column"
3. Map CSV column to button parameter

This is currently **not** implemented in the UI, so you'll need to:
- Either use the Python script above
- OR wait for frontend updates
- OR manually edit the code to hardcode the coupon column

## Temporary Workaround in app.py

If you want to hardcode the coupon code column for now, edit `app.py` around line 695:

```python
# Add button params before sending
button_params = {}

# TEMPORARY: Hardcode coupon code column
if "CouponCode" in row_dict:  # Replace with your CSV column name
    button_params["copy_code"] = str(row_dict["CouponCode"])

message_queue.add_message(
    send_template,
    phone,
    template_name,
    params,
    template_language,
    header_media_id=header_media_id,
    button_params=button_params if button_params else None,  # Add this line
    user_id=current_user.id,
    username=current_user.username,
    campaign_id=campaign_id,
    message_id=message_id
)
```

## Test Checklist

- [ ] Updated `utils/whatsapp.py` with new `button_params` parameter
- [ ] Updated `app.py` to extract and pass button parameters  
- [ ] CSV has coupon code column
- [ ] Template name is correct
- [ ] Test with single recipient first
- [ ] Check WhatsApp receives message with copy button
- [ ] Verify button copies the correct code

## Need Help?

1. **Find template details:**
   ```bash
   python -c "from utils.whatsapp import get_templates; from config import WABA_ID; import json; print(json.dumps(get_templates(WABA_ID), indent=2))"
   ```

2. **Test single message:**
   Use the `test_button_template.py` script above

3. **Check logs:**
   Look for the payload being sent in console output

## References

- Full documentation: `BUTTON_PARAMETERS_FIX.md`
- WhatsApp API: https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages#button-object
