# 🔍 Debugging Button Parameter Issues

## Current Error

```
ERROR: (#131008) Required parameter is missing
buttons: Button at index 1 of type copy_code requires a non-empty parameter coupon_code
```

## What This Means

The error shows the API is receiving the template request but `button_params` is either:
1. Not being passed at all
2. Being passed as `None`
3. Being passed as empty dictionary `{}`

## ✅ Debug Steps Added

I've added debug logging to `utils/whatsapp.py`. Now when you send a message, you'll see console output like:

**If button_params is received correctly:**
```
🔍 Button params received: {'copy_code': 'ITS2026BRO', 'copy_code_index': 1}
🔍 Auto-detected COPY_CODE button at index 1
📋 Adding COPY_CODE button: index=1, code=ITS2026BRO
```

**If button_params is missing:**
```
⚠️  button_params is None or empty!
```

**If copy_code key is missing:**
```
🔍 Button params received: {'some_other_key': 'value'}
⚠️  No 'copy_code' found in button_params!
```

---

## 🧪 Test Now

### Step 1: Start Flask App
```bash
python app.py
```

### Step 2: Send Test Message

1. Upload simple CSV:
   ```csv
   Name,Phone
   Test,+919702760931
   ```

2. Select `new_year_2025_campaign`

3. Fill fields:
   - Parameter 1 → Name
   - **Coupon Code** → `TEST123` ← Make sure you type something here!
   - Upload image

4. Click "Send Now"

### Step 3: Check Console Output

Look in the terminal where `python app.py` is running. You should see:

```
🔍 Button params received: {'copy_code': 'TEST123', 'copy_code_index': 1}
📋 Adding COPY_CODE button: index=1, code=TEST123
```

**Copy and paste what you see** in the console!

---

## 🔍 Common Issues

### Issue 1: Empty Coupon Code Field
**Symptoms:**
```
⚠️  button_params is None or empty!
```

**Cause**: You didn't type anything in the Coupon Code field

**Fix**: Make sure to type a coupon code in the dashboard form

---

### Issue 2: Form Field Not Being Sent
**Symptoms:**
```
🔍 Button params received: {}
⚠️  No 'copy_code' found in button_params!
```

**Cause**: The form field `name` doesn't match what backend expects

**Fix**: Check HTML form field name matches `button_coupon_code_{index}`

---

### Issue 3: Template Buttons Not Detected
**Symptoms:**
```
⚠️  button_params is None or empty!
```

**Cause**: `template_buttons` list is empty in app.py

**Check**: Look for this in console when selecting template:
```python
# In app.py around line 500, add:
print(f"🔍 Template buttons detected: {template_buttons}")
```

---

## 📋 Quick Diagnostic Checklist

Run through these:

1. **Check browser console (F12)**
   - Are there any JavaScript errors?
   - Does the coupon code field appear?

2. **Check form submission**
   - Right-click on page → Inspect
   - Go to Network tab
   - Click "Send Now"
   - Look for POST request
   - Check "Payload" tab - is `button_coupon_code_1` present?

3. **Check Flask console**
   - Look for debug messages starting with 🔍
   - What does "Button params received:" show?

4. **Check template structure**
   - Run: `python test_button_template.py`
   - Choose option 1
   - Find your template
   - Verify it shows button index correctly

---

## 🛠️ Temporary Manual Fix

If automatic detection isn't working, you can hardcode it temporarily in app.py:

Find line ~688 and add debug:

```python
# Before button_params extraction
print(f"🔍 Form data: {dict(request.form)}")
print(f"🔍 Template buttons: {template_buttons}")

# Prepare button parameters if template has buttons
button_params = {}
for btn in template_buttons:
    print(f"🔍 Processing button: {btn}")
    if btn["type"] == "COPY_CODE":
        coupon_code = request.form.get(btn["form_key"])
        print(f"🔍 Got coupon code from form: {coupon_code}")
        if coupon_code:
            button_params["copy_code"] = str(coupon_code)
            button_params["copy_code_index"] = btn["index"]

print(f"🔍 Final button_params: {button_params}")
```

This will show you exactly what's happening at each step.

---

## 📞 What to Share

When you test, please share:

1. **Console output** (the debug messages)
2. **Browser console errors** (F12 → Console tab)
3. **Network request payload** (F12 → Network → POST → Payload)
4. **Did you see the coupon code field** in the form?
5. **What did you type** in the coupon code field?

This will help me identify exactly where the issue is!

---

## 🎯 Expected Flow

**Correct flow should show:**

```
# When template selected
🔍 Template buttons detected: [{'index': 1, 'type': 'COPY_CODE', 'text': 'Copy Code', 'form_key': 'button_coupon_code_1'}]

# When form submitted
🔍 Form data: {'template_name': 'new_year_2025_campaign', 'param1': 'Name', 'button_coupon_code_1': 'TEST123', ...}
🔍 Got coupon code from form: TEST123
🔍 Final button_params: {'copy_code': 'TEST123', 'copy_code_index': 1}

# When sending
🔍 Button params received: {'copy_code': 'TEST123', 'copy_code_index': 1}
🔍 Auto-detected COPY_CODE button at index 1
📋 Adding COPY_CODE button: index=1, code=TEST123
✅ Message sent successfully
```

If any of these steps shows something different, that's where the problem is!
