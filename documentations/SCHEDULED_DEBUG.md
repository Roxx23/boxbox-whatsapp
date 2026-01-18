# 🔍 Debug: Scheduled Messages Button Parameters

## Issue Found

**Send Now**: ✅ Works - button parameters are passed correctly

**Send Later (Scheduled)**: ❌ Fails - button parameters NOT being passed

## Root Cause

The `button_params` variable needs to be captured by the scheduler's worker thread closure, but something is going wrong.

## Debug Output Added

I've added debug logging to trace the issue:

### In `utils/background_scheduler.py`:

**When scheduling:**
```python
print(f"🔍 schedule_message_job called with button_params: {button_params}")
```

**When worker starts:**
```python
print(f"🔍 Scheduler worker starting with button_params: {button_params}")
```

### In `utils/whatsapp.py`:

**When sending:**
```python
print(f"🔍 Button params received: {button_params}")
```

---

## Test Scheduled Message Again

### Step 1: Restart App
```bash
python app.py
```

### Step 2: Schedule Test Message

1. **Upload CSV:**
   ```csv
   Name,Phone
   Test,+919702760931
   ```

2. **Select template**: `new_year_2025_campaign`

3. **Fill fields:**
   - Parameter 1 → Name
   - **Coupon Code** → `TESTSCHEDULED`
   - Upload image

4. **Choose "Send Later"**

5. **Set time**: 1-2 minutes from now

6. **Click "Schedule"**

### Step 3: Check Console Output Immediately

Look for this line **right after clicking Schedule**:

```
🔍 schedule_message_job called with button_params: {'copy_code': 'TESTSCHEDULED', 'copy_code_index': 1}
```

**Copy and share this output!**

### Step 4: Wait for Scheduled Time

When the scheduled time arrives, look for:

```
🔍 Scheduler worker starting with button_params: {'copy_code': 'TESTSCHEDULED', 'copy_code_index': 1}
🔍 Button params received: {'copy_code': 'TESTSCHEDULED', 'copy_code_index': 1}
```

**Copy and share this too!**

---

## Expected vs Actual

### ✅ Expected Output (What Should Happen)

```
# When you click Schedule:
🔍 schedule_message_job called with button_params: {'copy_code': 'TESTSCHEDULED', 'copy_code_index': 1}

# When scheduled time arrives:
🔍 Scheduler worker starting with button_params: {'copy_code': 'TESTSCHEDULED', 'copy_code_index': 1}
🔍 Button params received: {'copy_code': 'TESTSCHEDULED', 'copy_code_index': 1}
📋 Adding COPY_CODE button: index=1, code=TESTSCHEDULED
✅ Message sent successfully
```

### ❌ If You See This (Problem)

```
# When you click Schedule:
🔍 schedule_message_job called with button_params: None

OR

# When scheduled time arrives:
🔍 Scheduler worker starting with button_params: None
⚠️  button_params is None or empty!
```

---

## Possible Issues

### Issue 1: button_params is None when scheduling

**Means**: `app.py` isn't extracting button params before calling scheduler

**Check**: Look at app.py around line 595-610 for button param extraction

### Issue 2: button_params is None when worker runs

**Means**: Python closure isn't capturing the variable

**Fix**: Store button_params in job_info dict instead of relying on closure

### Issue 3: button_params is empty dict {}

**Means**: Form field isn't being submitted or extracted correctly

**Check**: Browser Network tab → POST request → Payload

---

## Quick Fix to Try

If button_params is `None` when the worker runs but was valid when scheduling, add this to `utils/background_scheduler.py`:

**Around line 189 (in job_info dict):**

```python
# Create job info
job_info = {
    'job_id': job_id,
    'scheduled_time': send_time_str,
    'status': 'pending',
    'template_name': template_name,
    'message_template': message_template,
    'contact_count': len(df),
    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'button_params': button_params  # ADD THIS LINE
}
```

**Then in worker function around line 246:**

```python
def job_worker():
    # Get campaign_id and button_params from job_info
    campaign_id = job_info.get('campaign_id')
    stored_button_params = job_info.get('button_params')  # ADD THIS
    
    # Debug
    print(f"🔍 Scheduler worker starting with button_params: {stored_button_params}")
```

**And when sending around line 319:**

```python
message_queue.add_message(
    send_template,
    phone,
    template_name,
    params,
    template_language,
    header_media_id=header_media_id,
    button_params=stored_button_params,  # USE THIS INSTEAD
    user_id=user_id,
    username=username,
    campaign_id=campaign_id,
    message_id=message_id
)
```

---

## What to Share

Please run the test and share:

1. **Console output when you click Schedule**
2. **Console output when the scheduled time arrives**
3. **Any errors in browser console (F12)**

This will show us exactly where button_params is getting lost!

---

## Comparison

**Send Now** (working):
```
app.py extracts button_params → passes to message_queue → rate_limiter → send_template → WhatsApp API ✅
```

**Send Later** (not working):
```
app.py extracts button_params → passes to schedule_message_job → ??? → worker thread → send_template → WhatsApp API ❌
```

The ??? is where we need to check if button_params is being stored/accessed correctly.
