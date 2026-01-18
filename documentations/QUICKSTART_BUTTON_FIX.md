# 🚀 Quick Start: Fix Copy Code Button Error

## ⚡ Fastest Solution (1 minute)

### 1. Find Your Template Name
```bash
python test_button_template.py
```
Choose option 1 to list templates with buttons.

### 2. Test Send One Message
```bash
python test_button_template.py
```
Choose option 3 (interactive mode) and enter:
- Your template name
- Phone number: +919156143465
- Coupon code: SAVE20

### 3. ✅ Done!
Check your WhatsApp - you should receive the message with a working copy button.

---

## 📋 For Bulk Sending

### Option A: Hardcode Column (5 minutes)

1. **Prepare CSV** with coupon column:
   ```csv
   Name,Phone,CouponCode
   John,+919156143465,SAVE20
   ```

2. **Edit `app.py`** (around line 695):
   ```python
   # Add this BEFORE message_queue.add_message()
   button_params = {}
   if "CouponCode" in row_dict:  # Change "CouponCode" to your column name
       button_params["copy_code"] = str(row_dict["CouponCode"])
   ```

3. **Update the add_message call** to include:
   ```python
   message_queue.add_message(
       send_template,
       phone,
       template_name,
       params,
       template_language,
       header_media_id=header_media_id,
       button_params=button_params if button_params else None,  # ADD THIS
       user_id=current_user.id,
       username=current_user.username,
       campaign_id=campaign_id,
       message_id=message_id
   )
   ```

4. **Send** via dashboard as normal

### Option B: Python Script (2 minutes)

Create `send_bulk_with_coupon.py`:
```python
from utils.whatsapp import send_template
import pandas as pd

# Load CSV
df = pd.read_csv("contacts.csv")

# Send to each
for _, row in df.iterrows():
    send_template(
        number=row["Phone"],
        template_name="your_template_name",
        params=[],  # add if needed
        lang="en_US",
        button_params={"copy_code": row["CouponCode"]}
    )
    print(f"✅ Sent to {row['Phone']}")
```

Run: `python send_bulk_with_coupon.py`

---

## 🔍 Troubleshooting

### Error Still Occurs?
1. ✅ Updated `utils/whatsapp.py`? (Check line 27: `button_params=None`)
2. ✅ Passing `button_params` in app.py? (Check line ~710)
3. ✅ CSV has coupon column with values?
4. ✅ Template name is correct?

### Test Individual Components:
```python
# Test 1: Can you fetch templates?
from utils.whatsapp import get_templates
from config import WABA_ID
print(get_templates(WABA_ID))

# Test 2: Can you send without button?
from utils.whatsapp import send_template
send_template("+919156143465", "hello_world", [], "en")

# Test 3: Can you send WITH button?
send_template("+919156143465", "your_template", [], "en", button_params={"copy_code": "TEST"})
```

---

## 📚 Documentation Files

- **`BUTTON_FIX_SUMMARY.md`** - Complete technical summary
- **`BUTTON_PARAMETERS_FIX.md`** - Detailed documentation
- **`BUTTON_FIX_QUICK_GUIDE.md`** - Step-by-step guide
- **`test_button_template.py`** - Testing utility

---

## ✅ Changes Made

| File | Change | Status |
|------|--------|--------|
| `utils/whatsapp.py` | Added button_params support | ✅ Done |
| `app.py` | Extract & pass button params | ✅ Done |
| Test script | Created testing utility | ✅ Done |
| Frontend UI | Button param fields | ⚠️ TODO |
| Scheduler | Button param support | ⚠️ TODO |

---

## 🎯 Next Steps

1. **Test immediately**: Run `python test_button_template.py`
2. **For bulk**: Use Option A or B above
3. **Later**: Update frontend UI for better UX
4. **Optional**: Update scheduler for scheduled campaigns

---

## 💡 Key Insight

**The Problem**: WhatsApp requires button parameters in the API payload
**The Fix**: Pass `button_params={"copy_code": "VALUE"}` to `send_template()`

**Before**:
```python
send_template(phone, template, params, lang)  # ❌ Missing button params
```

**After**:
```python
send_template(phone, template, params, lang, button_params={"copy_code": "SAVE20"})  # ✅ Fixed
```

---

Need help? Check the detailed guides or run the test script!
