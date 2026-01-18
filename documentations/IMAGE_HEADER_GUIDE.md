# 🖼️ How to Handle Templates with IMAGE Headers

## Your Error Explained

**Error**: `(#132012) Parameter format does not match format in the created template`  
**Details**: `header: Format mismatch, expected IMAGE, received UNKNOWN`

**What this means**: Your template `new_year_2025_campaign` has an IMAGE header, but you didn't provide the image when sending the message.

---

## ✅ Solution: Provide header_media_id

When sending a template with IMAGE header, you MUST provide `header_media_id`:

```python
send_template(
    number=phone,
    template_name="new_year_2025_campaign",
    params=["Ayush"],
    lang="en",
    header_media_id="YOUR_MEDIA_ID_HERE",  # 👈 ADD THIS!
    button_params={"copy_code": "ITS2026BRO"}
)
```

---

## 📤 How to Upload Images

### Method 1: Upload from File

```python
from utils.whatsapp import upload_media

# Open your image file
with open("new_year_image.jpg", "rb") as img_file:
    # Create a file-like object
    from werkzeug.datastructures import FileStorage
    
    file_storage = FileStorage(
        stream=img_file,
        filename="new_year_image.jpg",
        content_type="image/jpeg"
    )
    
    # Upload to WhatsApp
    media_id = upload_media(file_storage)
    
    if media_id:
        print(f"✅ Image uploaded! Media ID: {media_id}")
        
        # Now send template with this media_id
        send_template(
            number="+919702760931",
            template_name="new_year_2025_campaign",
            params=["Ayush"],
            lang="en",
            header_media_id=media_id,
            button_params={"copy_code": "ITS2026BRO"}
        )
    else:
        print("❌ Image upload failed")
```

### Method 2: Upload via Direct API Call

```python
import requests
from config import ACCESS_TOKEN, PHONE_NUMBER_ID

def upload_image_direct(image_path):
    """Upload image directly and return media ID"""
    
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/media"
    
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }
    
    # Open and upload file
    with open(image_path, 'rb') as img_file:
        files = {
            'file': (image_path, img_file, 'image/jpeg')
        }
        
        data = {
            'messaging_product': 'whatsapp'
        }
        
        response = requests.post(url, headers=headers, files=files, data=data)
        
        if response.status_code in [200, 201]:
            media_id = response.json().get('id')
            print(f"✅ Uploaded! Media ID: {media_id}")
            return media_id
        else:
            print(f"❌ Upload failed: {response.json()}")
            return None

# Use it
media_id = upload_image_direct("new_year_image.jpg")
```

### Method 3: Use Previously Uploaded Media ID

If you already uploaded an image through the dashboard or Meta Business Manager, you can reuse that media ID:

```python
# Just use the media ID directly
REUSABLE_MEDIA_ID = "1234567890123456"  # Your existing media ID

send_template(
    number="+919702760931",
    template_name="new_year_2025_campaign",
    params=["Ayush"],
    lang="en",
    header_media_id=REUSABLE_MEDIA_ID,
    button_params={"copy_code": "ITS2026BRO"}
)
```

---

## 📝 Complete Example Script

Save as `send_with_image.py`:

```python
"""
Send template with IMAGE header and COPY_CODE button
"""

from utils.whatsapp import send_template, upload_media
from werkzeug.datastructures import FileStorage

# Step 1: Upload image (do this once)
def upload_header_image(image_path):
    """Upload image and return media ID"""
    try:
        with open(image_path, "rb") as img_file:
            file_storage = FileStorage(
                stream=img_file,
                filename=image_path.split("/")[-1],
                content_type="image/jpeg"  # or "image/png"
            )
            
            media_id = upload_media(file_storage)
            
            if media_id:
                print(f"✅ Image uploaded! Media ID: {media_id}")
                print(f"   Save this ID for reuse: {media_id}")
                return media_id
            else:
                print("❌ Upload failed")
                return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


# Step 2: Send template with image and button
def send_new_year_campaign(phone, name, coupon_code, header_media_id):
    """Send new year campaign template"""
    
    status, response = send_template(
        number=phone,
        template_name="new_year_2025_campaign",
        params=[name],  # For {{1}} in body
        lang="en",
        header_media_id=header_media_id,
        button_params={"copy_code": coupon_code}
    )
    
    if status == 200:
        print(f"✅ Message sent to {phone}!")
    else:
        print(f"❌ Failed: {response}")
    
    return status, response


# Main execution
if __name__ == "__main__":
    # Option 1: Upload new image
    # media_id = upload_header_image("new_year_image.jpg")
    
    # Option 2: Use existing media ID
    media_id = "YOUR_EXISTING_MEDIA_ID"  # Replace with actual ID
    
    if media_id:
        # Send to single recipient
        send_new_year_campaign(
            phone="+919702760931",
            name="Ayush",
            coupon_code="ITS2026BRO",
            header_media_id=media_id
        )
        
        # Or send to multiple recipients
        recipients = [
            {"phone": "+919702760931", "name": "Ayush", "code": "ITS2026BRO"},
            {"phone": "+919876543210", "name": "John", "code": "WELCOME2025"},
        ]
        
        for recipient in recipients:
            send_new_year_campaign(
                phone=recipient["phone"],
                name=recipient["name"],
                coupon_code=recipient["code"],
                header_media_id=media_id  # Same image for all
            )
            
            # Rate limiting
            import time
            time.sleep(1)
```

---

## 🔄 Using in Dashboard (app.py)

When sending from dashboard with IMAGE header templates, the image is already handled via the form upload. The issue is that button parameters weren't being passed.

**Current behavior**: Dashboard already handles image uploads  
**Fixed**: Now also passes button_params

For bulk sending with dashboard:
1. Upload CSV with coupon codes
2. If template has IMAGE header, upload image in the form
3. The dashboard will:
   - Upload image → get media_id
   - Extract coupon from CSV
   - Send with both header_media_id and button_params

---

## 🎯 Quick Fix for Your Specific Case

### Option 1: Upload Image Once, Save Media ID

```python
# Run this ONCE to get media ID
from utils.whatsapp import upload_media
from werkzeug.datastructures import FileStorage

with open("your_new_year_image.jpg", "rb") as f:
    file_obj = FileStorage(f, filename="image.jpg", content_type="image/jpeg")
    media_id = upload_media(file_obj)
    print(f"Media ID: {media_id}")  # Save this!
```

### Option 2: Send with Saved Media ID

```python
# Use saved media ID
from utils.whatsapp import send_template

send_template(
    number="+919702760931",
    template_name="new_year_2025_campaign",
    params=["Ayush"],
    lang="en",
    header_media_id="YOUR_SAVED_MEDIA_ID",  # Use the ID from option 1
    button_params={"copy_code": "ITS2026BRO"}
)
```

---

## 📊 Media ID Notes

- **Reusable**: Once uploaded, media ID can be reused for 30 days
- **Size Limit**: Max 5MB for images
- **Formats**: JPEG, PNG
- **Dimensions**: Min 800x800px recommended
- **No Expiry Messages**: If media ID expires, re-upload

---

## ❓ FAQ

**Q: Can I use a URL instead of media ID?**  
A: No. For sending messages, you MUST use media ID. URLs only work when creating templates.

**Q: How long does media ID last?**  
A: Media IDs are typically valid for 30 days.

**Q: Can I reuse same media ID for multiple messages?**  
A: Yes! Upload once, use many times (within 30 days).

**Q: Do I need to upload for each recipient?**  
A: No. Upload once, use same media_id for all recipients.

---

## 🚀 Next Steps

1. **Upload your New Year image** using Method 1 or 2 above
2. **Save the media_id** returned
3. **Update your sending script** to include `header_media_id`
4. **Test with one recipient** first
5. **Scale to bulk sending** once working

The button parameters fix is working correctly - you just need to add the image!
