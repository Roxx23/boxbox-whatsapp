# 🚀 Testing the Button Fix

## ⚠️ Before You Start

Make sure your `.env` file contains:

```env
WHATSAPP_ACCESS_TOKEN=your_access_token_here
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id_here
WABA_ID=your_waba_id_here
SECRET_KEY=your_secret_key_here
```

### How to Find Your WABA_ID

1. Go to [Meta Business Manager](https://business.facebook.com/)
2. Navigate to **WhatsApp Business Accounts**
3. Select your WhatsApp Business Account
4. The WABA_ID is in the URL: `https://business.facebook.com/wa/manage/home/?waba_id=XXXXXXXXXX`
5. Or find it in **Settings** → **WhatsApp Business Account ID**

---

## 🧪 Run Tests

### Option 1: Interactive Test Script
```bash
python test_button_template.py
```

**Features:**
- Option 1: List all templates with buttons
- Option 2: Test send (edit script values first)
- Option 3: Interactive mode (easiest - prompts for all values)

### Option 2: Code Examples
```bash
python examples_button_fix.py
```

**Features:**
- Example 1: Single message with copy code
- Example 2: Bulk from CSV
- Example 3: Body + Button parameters
- Example 4: Dynamic URL button
- Example 5: Multiple buttons

---

## 🎯 Quick Test (1 minute)

### Step 1: List Your Templates
```bash
python test_button_template.py
```
Choose **option 1** to see all templates with buttons.

### Step 2: Send Test Message
Choose **option 3** (Interactive mode) and enter:
- **Template name**: (from step 1)
- **Phone number**: Your WhatsApp number with country code (e.g., +919156143465)
- **Coupon code**: Any code you want (e.g., SAVE20)
- **Body params**: Leave empty if template has no {{1}}, {{2}}, etc.
- **Language**: Press Enter for default (en_US)

### Step 3: Check WhatsApp
You should receive a message with a **Copy Code** button that works!

---

## 🔧 Troubleshooting

### Error: "WABA_ID not found in .env file"
**Solution**: Add `WABA_ID=XXXXXXXXXX` to your `.env` file

### Error: "Template not found"
**Solution**: 
1. Check template name is correct (case-sensitive)
2. Make sure template is **approved** in Meta Business Manager
3. Use option 1 in test script to list available templates

### Error: "Authorization failed"
**Solution**: Check your `WHATSAPP_ACCESS_TOKEN` in `.env` is correct

### Error: "Required parameter missing - coupon_code"
**Solution**: This means the fix isn't being used. Make sure:
1. `utils/whatsapp.py` is updated (line 27 should have `button_params=None`)
2. You're passing `button_params={"copy_code": "VALUE"}` when calling send_template

### Template doesn't have buttons?
**Solution**: Create a new template in Meta Business Manager with:
- Category: **MARKETING** or **UTILITY**
- Add Button → **Copy offer code** (for COPY_CODE button)
- Or Button → **Visit website** with dynamic URL

---

## 📝 CSV Format for Bulk Sending

If using bulk send, your CSV should look like:

```csv
Name,Phone,CouponCode
John Doe,+919156143465,SAVE20
Jane Smith,+919876543210,WELCOME10
Bob Jones,+918765432109,FIRST15
```

**Required columns:**
- `Phone`: WhatsApp number with country code
- `CouponCode`: The coupon code to send (or whatever your button needs)

**Optional columns:**
- `Name`: If your template uses {{1}} for name
- Any other columns for template variables

---

## 🆘 Still Having Issues?

1. **Check the logs**: Look at console output for detailed error messages

2. **Verify template structure**: Run option 1 in test script to see button details

3. **Test without button first**: Try sending a simple template without buttons to verify your credentials work

4. **Manual test in Python console**:
   ```python
   from utils.whatsapp import send_template
   
   status, response = send_template(
       number="+919156143465",
       template_name="hello_world",  # Use a simple template first
       params=[],
       lang="en_US"
   )
   
   print(f"Status: {status}")
   print(f"Response: {response}")
   ```

5. **Check WhatsApp API status**: Visit [Meta Status Dashboard](https://status.fb.com/)

---

## 📚 More Documentation

- **`BUTTON_FIX_SUMMARY.md`** - Complete technical summary
- **`BUTTON_PARAMETERS_FIX.md`** - Detailed implementation
- **`BUTTON_FIX_QUICK_GUIDE.md`** - Step-by-step guide
- **`QUICKSTART_BUTTON_FIX.md`** - Fast solution

---

## ✅ Success Checklist

- [ ] `.env` file has all required variables (including WABA_ID)
- [ ] Template is approved in Meta Business Manager
- [ ] Template has COPY_CODE or dynamic URL button
- [ ] CSV has required columns (if bulk sending)
- [ ] Test script runs without errors
- [ ] WhatsApp message received with working button

---

**Happy testing! 🎉**
