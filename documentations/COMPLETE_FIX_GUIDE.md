# 🎯 Complete Fix Summary - Button Parameters + Image Headers

## Two Issues, Two Solutions

### Issue #1: Copy Code Button Error ✅ FIXED
**Error**: `(#131008) Required parameter is missing - coupon_code`  
**Solution**: Added `button_params` support to `send_template()`

### Issue #2: Image Header Error ✅ EXPLAINED
**Error**: `(#132012) Format mismatch, expected IMAGE, received UNKNOWN`  
**Solution**: Must provide `header_media_id` for templates with IMAGE headers

---

## Quick Solutions

### For Copy Code Button (Already Fixed)
```python
from utils.whatsapp import send_template

send_template(
    number="+919702760931",
    template_name="new_year_2025_campaign",
    params=["Ayush"],
    lang="en",
    button_params={"copy_code": "ITS2026BRO"}  # ✅ This is now working
)
```

### For Image Header (Need to Add)
```python
# Step 1: Upload image ONCE and save media ID
python upload_image.py your_image.jpg
# Returns: media_id = "1234567890"

# Step 2: Use media ID when sending
send_template(
    number="+919702760931",
    template_name="new_year_2025_campaign",
    params=["Ayush"],
    lang="en",
    header_media_id="1234567890",  # ✅ Add this
    button_params={"copy_code": "ITS2026BRO"}
)
```

---

## Your Specific Template: `new_year_2025_campaign`

Based on your error, this template has:
- ✅ **Header**: IMAGE format (needs media_id)
- ✅ **Body**: Has {{1}} parameter (needs params)
- ✅ **Button 1**: COPY_CODE (needs button_params)
- ✅ **Button 2**: URL call-to-action (no params needed)

### Complete Send Command
```python
from utils.whatsapp import send_template

# First, upload your New Year image
# Run: python upload_image.py new_year_2025.jpg
# Save the media_id returned

MEDIA_ID = "YOUR_MEDIA_ID_HERE"  # From upload

status, response = send_template(
    number="+919702760931",
    template_name="new_year_2025_campaign",
    params=["Ayush"],                    # For {{1}} in body
    lang="en",
    header_media_id=MEDIA_ID,            # For IMAGE header
    button_params={"copy_code": "ITS2026BRO"}  # For COPY_CODE button
)

if status == 200:
    print("✅ Message sent successfully!")
else:
    print(f"❌ Failed: {response}")
```

---

## Tools Available

### 1. Test Script (Updated)
```bash
python test_button_template.py
```
**Now includes:**
- ✅ Detects templates with IMAGE headers
- ✅ Prompts for header_media_id if needed
- ✅ Shows warning if image missing
- ✅ Handles button parameters

### 2. Image Upload Tool (New)
```bash
python upload_image.py
```
**Features:**
- Upload images to WhatsApp
- Get media ID instantly
- Save media IDs to file
- Validates file size/format

### 3. Examples Script
```bash
python examples_button_fix.py
```
**Shows how to:**
- Send single messages
- Bulk send from CSV
- Handle multiple button types

---

## Step-by-Step for Your Template

### Step 1: Upload Your Image
```bash
python upload_image.py path/to/new_year_image.jpg
```

**Output:**
```
✅ SUCCESS! Image uploaded
📋 MEDIA ID:
   1234567890123456

💾 Save this ID for use in your templates!
```

**Save this media ID!** You'll use it for all messages.

### Step 2: Test Single Message
```bash
python test_button_template.py
```

1. Choose option **3** (Interactive mode)
2. Enter template name: `new_year_2025_campaign`
3. Enter phone: `+919702760931`
4. Enter coupon code: `ITS2026BRO`
5. Enter body params: `Ayush`
6. **Enter header image ID**: `1234567890123456` (from Step 1)
7. Language: `en` (or press Enter for en_US)
8. Confirm and send

### Step 3: Bulk Send (Optional)

**CSV Format** (`contacts.csv`):
```csv
Name,Phone,CouponCode
Ayush,+919702760931,ITS2026BRO
John,+919876543210,WELCOME2025
Jane,+918765432109,NEWYEAR25
```

**Script** (`bulk_send_new_year.py`):
```python
from utils.whatsapp import send_template
import pandas as pd
import time

# Your saved media ID from Step 1
MEDIA_ID = "1234567890123456"

# Load CSV
df = pd.read_csv("contacts.csv")

# Send to each
for idx, row in df.iterrows():
    print(f"\n📤 Sending to {row['Name']} ({row['Phone']})...")
    
    status, response = send_template(
        number=row['Phone'],
        template_name="new_year_2025_campaign",
        params=[row['Name']],
        lang="en",
        header_media_id=MEDIA_ID,  # Same image for all
        button_params={"copy_code": row['CouponCode']}
    )
    
    if status == 200:
        print(f"   ✅ Sent successfully")
    else:
        print(f"   ❌ Failed: {response}")
    
    # Rate limiting
    time.sleep(1)

print("\n✅ Bulk send complete!")
```

Run:
```bash
python bulk_send_new_year.py
```

---

## Understanding the Fixes

### Fix #1: Button Parameters (In Code)
**Changed Files:**
- `utils/whatsapp.py` - Added button_params parameter
- `app.py` - Extract and pass button params

**How it works:**
```python
# Before (ERROR)
components = [
    {"type": "body", "parameters": [...]}
]

# After (FIXED)
components = [
    {"type": "body", "parameters": [...]},
    {
        "type": "button",
        "sub_type": "copy_code",
        "index": "0",
        "parameters": [
            {"type": "coupon_code", "coupon_code": "ITS2026BRO"}
        ]
    }
]
```

### Fix #2: Image Headers (Usage)
**No code change needed** - just provide the parameter:

```python
# Before (ERROR)
send_template(..., button_params={...})

# After (FIXED)
send_template(..., header_media_id="123", button_params={...})
```

---

## Media ID Best Practices

### Upload Once, Use Many Times
```python
# Upload once
MEDIA_ID = upload_image("new_year.jpg")  # Save this!

# Use for all recipients
for recipient in recipients:
    send_template(..., header_media_id=MEDIA_ID, ...)  # Reuse
```

### Save Your Media IDs
Keep a file `media_ids.txt`:
```
new_year_2025.jpg → 1234567890123456 (uploaded 2025-12-27)
christmas_promo.png → 9876543210987654 (uploaded 2025-12-25)
```

### Media ID Expiry
- Valid for ~30 days
- If expired, re-upload and update media_id
- No way to list uploaded media (save IDs manually)

---

## Checklist for Success

- [ ] ✅ Button parameters fix applied (`utils/whatsapp.py` updated)
- [ ] ✅ Test script updated for image headers
- [ ] ✅ Image upload tool created
- [ ] 📤 Upload your New Year image
- [ ] 💾 Save the media_id returned
- [ ] 🧪 Test single message with test script
- [ ] 📊 Prepare CSV with contacts and coupon codes
- [ ] 🚀 Run bulk send script
- [ ] ✅ Verify messages received with:
  - ✅ Image header
  - ✅ Personalized body text
  - ✅ Working copy code button
  - ✅ URL button (if in template)

---

## Documentation Reference

| Document | Purpose |
|----------|---------|
| `BUTTON_FIX_SUMMARY.md` | Button parameters technical details |
| `IMAGE_HEADER_GUIDE.md` | Complete guide for IMAGE headers |
| `TESTING_GUIDE.md` | How to test and troubleshoot |
| `QUICKSTART_BUTTON_FIX.md` | Quick start for button fix |
| `BUTTON_PARAMETERS_FIX.md` | Detailed implementation |

---

## Common Errors

| Error Code | Message | Solution |
|------------|---------|----------|
| 131008 | Button parameter missing | Use button_params={"copy_code": "X"} |
| 132012 | Format mismatch (IMAGE) | Use header_media_id="X" |
| 131009 | Parameter count mismatch | Check body params match {{1}}, {{2}} |
| 404 | Template not found | Verify template name |
| 401 | Authorization failed | Check ACCESS_TOKEN |

---

## Need Help?

1. **List your templates:**
   ```bash
   python test_button_template.py
   # Choose option 1
   ```

2. **Upload an image:**
   ```bash
   python upload_image.py your_image.jpg
   ```

3. **Test single message:**
   ```bash
   python test_button_template.py
   # Choose option 3
   ```

4. **Check documentation:**
   - See `IMAGE_HEADER_GUIDE.md` for image details
   - See `TESTING_GUIDE.md` for troubleshooting

---

**You're all set! 🎉**

Both fixes are ready:
- ✅ Button parameters work
- ✅ Tools available for image upload
- ✅ Test scripts updated
- ✅ Documentation complete

Just upload your image and you're good to go!
