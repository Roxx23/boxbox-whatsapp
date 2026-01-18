# Reply and Click Tracking Debug Guide

## What I Fixed

Added better logging and fallback matching for replies without context.

### Updates:
1. **Better Logging** - See exactly what webhook receives
2. **Phone Number Matching** - Match replies even without context
3. **Detailed Error Messages** - Know exactly what's wrong

## How to Test Reply Tracking

### Step 1: Restart Flask
```bash
# Stop Flask (Ctrl+C)
python app.py
```

### Step 2: Send a Message
1. Send a message to someone from dashboard
2. Note the phone number

### Step 3: Reply to the Message
Have the recipient reply on WhatsApp

### Step 4: Watch Flask Terminal
You should see ONE of these patterns:

**Pattern A: Reply with Context (Best)**
```
📥 Webhook received: {...}
📨 Processing 1 incoming messages
📨 Incoming message from 1234567890, type: text
💬 Reply with context to message: wamid.xxx
✅ Reply tracking updated for: wamid.xxx
✅ Updated replied count for campaign X
```

**Pattern B: Reply without Context (Fallback)**
```
📥 Webhook received: {...}
📨 Processing 1 incoming messages
📨 Incoming message from 1234567890, type: text
💬 Reply without context from 1234567890
✅ Reply matched to message ID: wamid.xxx
✅ Updated replied count for campaign X
```

**Pattern C: Reply Not Matched**
```
📥 Webhook received: {...}
📨 Processing 1 incoming messages
📨 Incoming message from 1234567890, type: text
💬 Reply without context from 1234567890
⚠️ No recent message found for 1234567890
```

## Troubleshooting

### Issue: Not seeing "Processing incoming messages"
**Problem:** Webhook not receiving message updates

**Solution:**
1. Check Meta Developer Console
2. Webhook → Webhooks fields
3. Make sure **"messages"** is subscribed (not just "message_status")
4. Click "Subscribe"

### Issue: Seeing "No recent message found"
**Problem:** Phone number doesn't match

**Possible reasons:**
- Message older than 24 hours
- Phone number format different (e.g., +1234 vs 1234)
- Message already marked as replied

**Solution:**
```bash
# Check database for recent messages
python -c "
import sqlite3
conn = sqlite3.connect('whatsapp_dashboard.db')
cursor = conn.cursor()
cursor.execute('''
    SELECT phone_number, sent_at, replied_at, whatsapp_message_id 
    FROM messages 
    WHERE sent_at > datetime('now', '-24 hours')
    ORDER BY sent_at DESC
    LIMIT 5
''')
for row in cursor.fetchall():
    print(row)
"
```

### Issue: Reply matched but count not increasing
**Problem:** Database update failed

**Check:**
```bash
python debug_engagement.py
```

Look for:
```
Replied Messages: X  ← Should be > 0
```

### Issue: Button clicks not working
**Problem:** Using regular text messages (buttons only work with templates)

**Solution:**
- Buttons only work with **approved template messages** that have buttons
- Regular text messages don't have clickable buttons
- Interactive messages need special WhatsApp API setup

## WhatsApp Message Types

### Text Reply (Tracked ✅)
```
User: "Thanks for the info!"
→ Tracked as replied
```

### Button Click (Tracked ✅ - if using template)
```
Template with buttons:
[Button 1] [Button 2]
User clicks → Tracked as clicked
```

### Media Reply (Tracked ✅)
```
User sends image/video/document as reply
→ Tracked as replied
```

## Testing Checklist

- [ ] Restart Flask
- [ ] Send message from dashboard
- [ ] Reply to message on WhatsApp
- [ ] Check Flask terminal for logs
- [ ] Check Analytics page for replied count
- [ ] Run `python debug_engagement.py`

## Common Webhook Payload for Reply

```json
{
  "entry": [{
    "changes": [{
      "value": {
        "messages": [{
          "from": "1234567890",
          "id": "wamid.xxx",
          "timestamp": "1234567890",
          "type": "text",
          "text": {
            "body": "Thanks!"
          },
          "context": {
            "from": "YOUR_NUMBER",
            "id": "wamid.ORIGINAL_MESSAGE"  ← This links to your message
          }
        }]
      }
    }]
  }]
}
```

**If `context` is missing:** Uses phone number matching fallback

## Expected Behavior

### After Sending 10 Messages and Getting 3 Replies:

**Database:**
```sql
SELECT replied_count FROM campaigns ORDER BY id DESC LIMIT 1;
→ 3
```

**Analytics Page:**
```
Replied: 3 (30.0%)
```

**Engagement Funnel:**
```
💬 Replied ██████ 3 30.0%
```

## Quick Test Command

```bash
# Watch Flask logs in real-time
python app.py

# In another terminal, send a message
# Then reply to it on WhatsApp
# Watch the first terminal for logs
```

## Need More Help?

Share the Flask terminal output when you reply to a message, especially:
- The full webhook payload
- Any error messages
- The log lines about "Processing incoming messages"

This will show exactly what's happening! 🔍
