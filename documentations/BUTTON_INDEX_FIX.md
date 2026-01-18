# 🔧 Button Index Fix - Auto-Detection

## The Problem

Your template `new_year_2025_campaign` has buttons in this order:
1. **Button 0**: URL button (call-to-action)
2. **Button 1**: COPY_CODE button (utility)

But the code was hardcoded to use index "0" for COPY_CODE, causing error:
```
(#132018) Button at index 0 of type Url does not require parameters
```

## ✅ Solution Applied

The code now **auto-detects** the correct button index by:
1. Fetching the template structure from WhatsApp API
2. Finding which index the COPY_CODE button is at
3. Using that index when sending

### Code Changes

**File**: `utils/whatsapp.py`

```python
# Now automatically detects button index
if WABA_ID:
    templates = get_templates(WABA_ID)
    template = next((t for t in templates if t["name"] == template_name), None)
    
    if template:
        buttons_comp = next((c for c in template["components"] if c["type"] == "BUTTONS"), None)
        if buttons_comp:
            for idx, btn in enumerate(buttons_comp["buttons"]):
                if btn.get("type") == "COPY_CODE":
                    index = str(idx)  # Found it!
                    break
```

## 🚀 How to Use

### Option 1: Auto-Detection (Recommended)

Just use normally - it will auto-detect:

```python
send_template(
    number="+919702760931",
    template_name="new_year_2025_campaign",
    params=["Ayush"],
    lang="en",
    header_media_id="825914237107605",
    button_params={"copy_code": "ITS2026BRO"}  # Index auto-detected!
)
```

The console will show:
```
🔍 Auto-detected COPY_CODE button at index 1
```

### Option 2: Manual Index (If Auto-Detection Fails)

Specify the index explicitly:

```python
send_template(
    number="+919702760931",
    template_name="new_year_2025_campaign",
    params=["Ayush"],
    lang="en",
    header_media_id="825914237107605",
    button_params={
        "copy_code": "ITS2026BRO",
        "copy_code_index": 1  # Explicitly set index
    }
)
```

## 📝 Testing

Run your test again:

```bash
python test_button_template.py
```

Choose option 3, enter:
- Template: `new_year_2025_campaign`
- Phone: `+919702760931`
- Coupon: `ITS2026BRO`
- Body params: `Ayush`
- Header image ID: `825914237107605`
- Language: `en`

You should see:
```
🔍 Auto-detected COPY_CODE button at index 1
✅ Status: 200
✅ SUCCESS! Message sent successfully
```

## 🎯 Expected Payload

The correct payload will now be:

```json
{
  "components": [
    {
      "type": "header",
      "parameters": [{"type": "image", "image": {"id": "825914237107605"}}]
    },
    {
      "type": "body",
      "parameters": [{"type": "text", "text": "Ayush"}]
    },
    {
      "type": "button",
      "sub_type": "copy_code",
      "index": "1",  // ← Changed from "0" to "1"
      "parameters": [{
        "type": "coupon_code",
        "coupon_code": "ITS2026BRO"
      }]
    }
  ]
}
```

## 🔍 How to Find Button Order

If you want to manually check your template's button order:

```bash
python test_button_template.py
# Choose option 1 to list templates
```

Look for your template output:
```
📌 Template: new_year_2025_campaign
   Buttons:
      1. [URL] Visit Website        ← Index 0
      2. [COPY_CODE] Copy Code      ← Index 1
         → Requires: coupon_code parameter
```

## ⚠️ Important Notes

### Button Index Rules
- **Buttons are 0-indexed** (first button = 0, second = 1, etc.)
- **URL buttons** (static) don't need parameters
- **COPY_CODE buttons** need coupon_code parameter
- **URL buttons with {{1}}** need url_index_X parameter

### Common Button Orders

**Order 1**: CTA first, Utility second
```
Button 0: URL (no params)
Button 1: COPY_CODE (needs params) ← Your template
```

**Order 2**: Utility first, CTA second
```
Button 0: COPY_CODE (needs params)
Button 1: URL (no params)
```

**Order 3**: Multiple CTAs
```
Button 0: URL (no params)
Button 1: URL (no params)
Button 2: COPY_CODE (needs params)
```

## 🐛 Troubleshooting

### Error: "Button at index X of type Y does not require parameters"

**Cause**: Wrong button index specified

**Solutions**:
1. Let auto-detection handle it (remove `copy_code_index`)
2. Check template button order with option 1
3. Manually specify correct index

### Auto-Detection Not Working

**Possible causes**:
- WABA_ID not in .env file
- Template name typo
- Network issue fetching templates

**Fallback**: Specify index manually:
```python
button_params={
    "copy_code": "ITS2026BRO",
    "copy_code_index": 1  # Your specific index
}
```

### Multiple COPY_CODE Buttons

If template has multiple COPY_CODE buttons (rare):

```python
# First COPY_CODE button (index 1)
button_params={
    "copy_code": "ITS2026BRO",
    "copy_code_index": 1
}

# For second COPY_CODE button (index 2):
button_params={
    "copy_code": "BONUS50",
    "copy_code_index": 2
}
```

Currently only supports ONE copy_code button per template.

## ✅ Status

- ✅ Auto-detection implemented
- ✅ Manual index override supported
- ✅ Error messages improved
- ✅ Works with any button order

## 🚀 Try It Now

Your template should now work perfectly. Run:

```bash
python test_button_template.py
```

And send a test message!

---

**The fix is complete and should work automatically!** 🎉
