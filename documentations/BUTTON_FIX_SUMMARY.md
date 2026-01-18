# Summary: Button Parameters Fix Applied

## Problem Solved
❌ **Error**: `(#131008) Required parameter is missing - buttons: Button at index 1 of type copy_code requires a non-empty parameter coupon_code`

✅ **Solution**: Added support for button parameters (copy_code, dynamic URLs) in template sending

---

## Files Modified

### 1. `utils/whatsapp.py`
**Function**: `send_template()`

**Changes**:
- Added `button_params` parameter to function signature
- Added logic to build button components for WhatsApp API
- Supports `COPY_CODE` buttons (coupon codes)
- Supports dynamic URL buttons with parameters

**Before**:
```python
def send_template(number, template_name, params, lang="en_US", header_media_id=None)
```

**After**:
```python
def send_template(number, template_name, params, lang="en_US", header_media_id=None, button_params=None)
```

### 2. `app.py`
**Changes Made**:

#### A. Enhanced template info endpoint
```python
@app.route("/template-info")
def template_info():
    # Now returns button information
    return jsonify({
        "count": 2,
        "buttons": [
            {"index": 0, "type": "COPY_CODE", "text": "Copy Code", "requires": "coupon_code"}
        ]
    })
```

#### B. Extract button info when loading template
```python
# Around line 485-520
template_buttons = []
buttons_component = next(
    (c for c in selected_template["components"] if c["type"] == "BUTTONS"),
    None
)
if buttons_component:
    for idx, btn in enumerate(buttons_component["buttons"]):
        if btn["type"] == "COPY_CODE":
            template_buttons.append({
                "index": idx,
                "type": "COPY_CODE",
                "form_key": f"button_coupon_code_{idx}"
            })
```

#### C. Build button params when sending messages
```python
# Around line 695-715
button_params = {}
for btn in template_buttons:
    if btn["type"] == "COPY_CODE":
        coupon_col = request.form.get(btn["form_key"])
        if coupon_col:
            coupon_value = row_dict.get(coupon_col)
            if coupon_value:
                button_params["copy_code"] = str(coupon_value)

message_queue.add_message(
    send_template,
    phone,
    template_name,
    params,
    template_language,
    button_params=button_params if button_params else None,
    # ... other params
)
```

---

## Files Created

### 1. `BUTTON_PARAMETERS_FIX.md`
Comprehensive technical documentation covering:
- Root cause analysis
- Solution implementation details
- API payload structure
- Button types supported
- Frontend changes needed (TODO)
- Testing guide

### 2. `BUTTON_FIX_QUICK_GUIDE.md`
Quick reference guide with:
- Immediate workaround steps
- Manual API test code
- CSV format examples
- Troubleshooting tips
- Temporary hardcode solution

### 3. `test_button_template.py`
Testing utility script with:
- List all templates with buttons
- Test send function
- Interactive mode for testing
- Helpful error messages

---

## How It Works

### WhatsApp API Payload Structure

**Complete payload with button parameters:**
```json
{
  "messaging_product": "whatsapp",
  "to": "919156143465",
  "type": "template",
  "template": {
    "name": "promo_template",
    "language": {"code": "en_US"},
    "components": [
      {
        "type": "body",
        "parameters": [
          {"type": "text", "text": "John"}
        ]
      },
      {
        "type": "button",
        "sub_type": "copy_code",
        "index": "0",
        "parameters": [
          {
            "type": "coupon_code",
            "coupon_code": "SAVE20"
          }
        ]
      }
    ]
  }
}
```

### Code Flow

1. **Template Selection** → Extract button info from template structure
2. **CSV Upload** → User maps coupon code column
3. **Message Preparation** → Extract coupon value from CSV row
4. **API Call** → Include button component in payload
5. **WhatsApp Delivery** → User receives message with copy button

---

## Testing

### Quick Test (Immediate)

1. **Run the test script**:
   ```bash
   python test_button_template.py
   ```

2. **Choose option 3** (Interactive mode)

3. **Enter details**:
   - Template name (your template with copy_code button)
   - Phone number
   - Coupon code (e.g., SAVE20)

4. **Verify**: Check WhatsApp message received

### Manual Test Code

```python
from utils.whatsapp import send_template

status, response = send_template(
    number="+919156143465",
    template_name="your_template_name",
    params=[],  # body parameters
    lang="en_US",
    button_params={"copy_code": "SAVE20"}
)

print(f"Status: {status}, Response: {response}")
```

---

## What's Still TODO

### Frontend UI Updates (Not Yet Implemented)

The backend is ready, but the UI needs these changes:

1. **Detect button requirements**:
   - When user selects template, call `/template-info`
   - Check if `buttons` array has any items

2. **Show button parameter fields**:
   ```html
   <!-- If COPY_CODE button detected -->
   <div class="form-group">
       <label>Coupon Code Column:</label>
       <select name="button_coupon_code_0">
           <option value="">Select column...</option>
           <!-- CSV columns populated here -->
       </select>
   </div>
   ```

3. **Update JavaScript**:
   ```javascript
   $('#template_name').change(function() {
       $.get('/template-info?name=' + $(this).val(), function(data) {
           if (data.buttons && data.buttons.length > 0) {
               // Show button parameter fields
           }
       });
   });
   ```

### Scheduler Integration (Pending)

Update `utils/background_scheduler.py`:
- Add `button_params_mapping` to `schedule_message_job()`
- Extract button values from CSV when scheduled job runs
- Pass to `send_template()` calls

---

## Current Workaround

### Option 1: Hardcode Column (Temporary)

Edit `app.py` around line 695:

```python
# Before message_queue.add_message()
button_params = {}

# HARDCODE: Replace "CouponCode" with your CSV column name
if "CouponCode" in row_dict:
    button_params["copy_code"] = str(row_dict["CouponCode"])

message_queue.add_message(
    send_template,
    # ...
    button_params=button_params if button_params else None,
    # ...
)
```

### Option 2: Use Test Script

Use `test_button_template.py` to send individual messages until UI is updated.

---

## Verification Checklist

- ✅ `send_template()` accepts `button_params`
- ✅ Button components added to API payload
- ✅ COPY_CODE button support implemented
- ✅ Dynamic URL button support implemented
- ✅ `/template-info` returns button info
- ✅ Message queue passes button_params
- ✅ Test script created
- ✅ Documentation created
- ⚠️ Frontend UI not updated (manual workaround needed)
- ⚠️ Scheduler not updated (scheduled messages won't have buttons)

---

## Error Code Reference

| Error Code | Message | Solution |
|------------|---------|----------|
| 131008 | Required parameter missing | Add button_params to send_template() |
| 131009 | Parameter count mismatch | Check body params match template {{1}}, {{2}}, etc. |
| 404 | Template not found | Verify template name is correct |
| 401 | Authorization failed | Check ACCESS_TOKEN in .env |

---

## Support

If you still encounter issues:

1. **Check template structure**:
   ```bash
   python test_button_template.py
   # Choose option 1 to list templates
   ```

2. **Test single message first**:
   ```bash
   python test_button_template.py
   # Choose option 3 for interactive test
   ```

3. **Review logs**: Check console output for API payload being sent

4. **Verify CSV format**: Ensure coupon column exists and has values

---

## References

- WhatsApp Docs: https://developers.facebook.com/docs/whatsapp/cloud-api/guides/send-message-templates
- Button Components: https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages#button-object
- Template Components: https://developers.facebook.com/docs/whatsapp/business-management-api/message-templates/components

---

**Status**: Backend complete ✅ | Frontend pending ⚠️ | Testing script ready ✅
