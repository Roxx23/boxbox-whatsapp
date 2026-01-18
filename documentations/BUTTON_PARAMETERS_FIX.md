# Button Parameters Fix - Copy Code & Dynamic URL Buttons

## Problem
Error when sending templates with special button types:
```
ERROR: (#131008) Required parameter is missing
buttons: Button at index 1 of type copy_code requires a non-empty parameter coupon_code
```

## Root Cause
WhatsApp templates with **utility buttons** (like `COPY_CODE` for coupon codes) or **dynamic URL buttons** require additional parameters when sending messages. The original `send_template()` function only handled:
- Header parameters (images)
- Body parameters (text variables)
- ❌ **Missing**: Button parameters

## Solution Applied

### 1. Updated `utils/whatsapp.py` - `send_template()` function

Added `button_params` argument to handle button-specific parameters:

```python
def send_template(number, template_name, params, lang="en_US", 
                  header_media_id=None, button_params=None):
    """
    Args:
        button_params: Optional dict with button parameters, e.g.:
            {"copy_code": "SAVE20"} for coupon code button
            {"url_index_0": "param1"} for dynamic URL button parameters
    """
```

**Button Component Structure:**
```python
# For COPY_CODE buttons (e.g., coupon codes)
if "copy_code" in button_params:
    button_components.append({
        "type": "button",
        "sub_type": "copy_code",
        "index": "0",
        "parameters": [{
            "type": "coupon_code",
            "coupon_code": str(button_params["copy_code"])
        }]
    })

# For dynamic URL buttons (with variables)
if key.startswith("url_index_"):
    index = key.split("_")[-1]
    button_components.append({
        "type": "button",
        "sub_type": "url",
        "index": index,
        "parameters": [{
            "type": "text",
            "text": str(value)
        }]
    })
```

### 2. Updated `app.py` - Template Info Endpoint

Enhanced `/template-info` to detect and return button requirements:

```python
@app.route("/template-info")
def template_info():
    # Returns:
    return jsonify({
        "count": 2,  # body parameter count
        "buttons": [
            {
                "index": 0,
                "type": "COPY_CODE",
                "text": "Copy Code",
                "requires": "coupon_code"
            }
        ]
    })
```

### 3. Updated `app.py` - Message Sending Logic

Extracts button parameters from form data and passes to `send_template()`:

```python
# Extract button information from template
template_buttons = []
if buttons_component:
    for idx, btn in enumerate(buttons_component["buttons"]):
        if btn["type"] == "COPY_CODE":
            template_buttons.append({
                "index": idx,
                "type": "COPY_CODE",
                "form_key": f"button_coupon_code_{idx}"
            })

# When sending messages
for row in df.iterrows():
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
        button_params=button_params if button_params else None
    )
```

## Button Types Supported

### 1. COPY_CODE (Utility Button)
**Use Case**: Promotional coupon codes that users can copy

**Template Button Config:**
```json
{
  "type": "COPY_CODE",
  "text": "Copy Code",
  "example": ["SAVE20"]
}
```

**Required Parameter:**
- `coupon_code`: The actual coupon code value (e.g., "SAVE20", "WELCOME10")

**Usage in CSV:**
```csv
Name,Phone,CouponCode
John,+1234567890,SAVE20
Jane,+1234567891,WELCOME10
```

Then map `CouponCode` column to the button parameter in the UI.

### 2. URL with Variables (Call to Action)
**Use Case**: Personalized URLs with dynamic parameters

**Template Button Config:**
```json
{
  "type": "URL",
  "text": "View Order",
  "url": "https://example.com/order/{{1}}"
}
```

**Required Parameter:**
- `url_index_0`: Value to replace `{{1}}` in URL (e.g., order ID)

## Frontend Changes Needed (TODO)

The backend now supports button parameters, but the frontend UI needs updates:

### In `templates/index.html`:

1. **Detect buttons when template is selected:**
```javascript
// When template changes
$('#template_name').change(function() {
    $.get('/template-info?name=' + $(this).val(), function(data) {
        // data.buttons contains button info
        data.buttons.forEach(btn => {
            if (btn.type === 'COPY_CODE') {
                // Show field: "Map coupon code column:"
            }
        });
    });
});
```

2. **Add form fields for button parameters:**
```html
<!-- If COPY_CODE button detected -->
<div class="form-group">
    <label>Coupon Code Column:</label>
    <select name="button_coupon_code_0">
        <option value="">Select column...</option>
        <!-- CSV columns -->
    </select>
</div>
```

3. **Add to scheduled messages form:**
Similar fields need to be added to the scheduling UI.

## Testing

### Test Template with COPY_CODE button:

1. **Create template in Meta Business Manager:**
   - Category: MARKETING
   - Body: "Use code {{1}} for 20% off!"
   - Button 1 (Utility): COPY_CODE - "Copy Code"
   - Button 2 (CTA): URL - "Shop Now" → https://example.com

2. **CSV format:**
```csv
Name,Phone,DiscountCode
John,+1234567890,SAVE20
Jane,+1234567891,WELCOME10
```

3. **Send via dashboard:**
   - Select template
   - Upload CSV
   - Map parameter 1 → Name
   - Map "Coupon Code Column" → DiscountCode
   - Send

### Expected API Payload:
```json
{
  "messaging_product": "whatsapp",
  "to": "1234567890",
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
          {"type": "coupon_code", "coupon_code": "SAVE20"}
        ]
      }
    ]
  }
}
```

## References

- [WhatsApp Cloud API - Message Templates](https://developers.facebook.com/docs/whatsapp/cloud-api/guides/send-message-templates)
- [Button Components Documentation](https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages#button-object)
- [Template Components](https://developers.facebook.com/docs/whatsapp/business-management-api/message-templates/components)

## Common Button Types

| Button Type | Sub Type | Required Parameters | Example |
|-------------|----------|-------------------|---------|
| COPY_CODE | `copy_code` | `coupon_code` | "SAVE20" |
| URL (static) | `url` | None | Fixed URL |
| URL (dynamic) | `url` | URL parameters | Order ID, tracking # |
| PHONE_NUMBER | `phone_number` | None | Fixed number |
| QUICK_REPLY | N/A | None | Simple text |

## Status
- ✅ Backend support implemented
- ✅ API integration complete
- ⚠️ Frontend UI updates needed
- ⚠️ Scheduler integration pending

## Next Steps

1. **Update frontend (templates/index.html)**:
   - Detect button requirements via `/template-info`
   - Add form fields for button parameter mapping
   - Update JavaScript to handle button parameters

2. **Update scheduler** (`utils/background_scheduler.py`):
   - Add `button_params_mapping` argument
   - Extract button values from CSV rows
   - Pass to `send_template()` calls

3. **Testing**:
   - Create test templates with different button types
   - Test with sample CSV data
   - Verify WhatsApp API accepts payloads

4. **Documentation**:
   - Add user guide for button parameters
   - Screenshot examples of UI fields
   - Troubleshooting common errors
