# Advanced Message Scheduling - Complete Guide

## 🎯 What's New

You can now schedule messages for:
- ✅ **Specific dates** (days, weeks, or months in advance)
- ✅ **Specific times** (any time of day)
- ✅ **Automatic sending** (works even when logged out)

## 📅 Schedule Options

### Before (Limited):
```
✗ Only "today" or "tomorrow" at a specific time
✗ Had to calculate if time was in past/future
✗ No date selection
```

### After (Powerful):
```
✅ Select any future date
✅ Select any time
✅ Visual date/time picker
✅ Automatic validation
✅ Works even when logged out
```

---

## 🖥️ How to Use

### Step 1: Upload CSV
Upload your contacts as usual

### Step 2: Choose "Schedule Later"
Select the "Schedule Later" radio button

### Step 3: Pick Date & Time
```
┌─────────────────────────────────────┐
│ Schedule Date & Time                │
├─────────────────────────────────────┤
│ Date: [2025-12-30]  📅              │
│ Time: [14:30]       🕐              │
│                                     │
│ ⚠️ Note: Messages will be sent     │
│ automatically even when you're      │
│ logged out.                         │
└─────────────────────────────────────┘
```

### Step 4: Click "Start Sending Messages"
Your messages are scheduled!

---

## 📋 Examples

### Example 1: Schedule for Tomorrow
```
Today: December 27, 2025 at 10:00 AM

Schedule for:
Date: 2025-12-28
Time: 14:00

Result: Messages sent December 28 at 2:00 PM
Time until: 1 day, 4 hours
```

### Example 2: Schedule for Next Week
```
Today: December 27, 2025

Schedule for:
Date: 2026-01-03
Time: 09:00

Result: Messages sent January 3 at 9:00 AM
Time until: 7 days
```

### Example 3: Schedule for Next Month
```
Today: December 27, 2025

Schedule for:
Date: 2026-01-27
Time: 10:00

Result: Messages sent January 27 at 10:00 AM
Time until: 31 days
```

### Example 4: Schedule for 3 Days Later
```
Today: December 27, 2025 at 3:00 PM

Schedule for:
Date: 2025-12-30
Time: 10:00

Result: Messages sent December 30 at 10:00 AM
Time until: 2 days, 19 hours
```

---

## ✅ Features

### 1. Date Picker
```
📅 Visual calendar
✓ Can't select past dates
✓ Shows month/year
✓ Easy navigation
```

### 2. Time Picker
```
🕐 24-hour format
✓ Select hours and minutes
✓ Dropdown interface
✓ Clear display
```

### 3. Smart Validation
```
✅ Checks if date/time is in future
✅ Prevents past scheduling
✅ Clear error messages
✅ User-friendly feedback
```

### 4. Time Calculation
```
Shows: "in 3 days and 5 hours"

Examples:
- Less than 1 hour: "in 45 minutes"
- Less than 1 day: "in 5 hours and 30 minutes"
- Multiple days: "in 7 days and 3 hours"
```

### 5. Background Processing
```
✅ Runs independently
✅ Works when logged out
✅ Server restarts don't affect it
✅ Persistent scheduling
```

---

## 🔧 Technical Details

### Date Format
```
Input: YYYY-MM-DD HH:MM
Example: 2025-12-30 14:30
```

### Supported Formats
```
✅ Full datetime: "2025-12-30 14:30"
✅ Time only: "14:30" (for today/tomorrow)
```

### Validation Rules
```
1. Date must be today or in future
2. Time must be in future (if date is today)
3. Both date and time required
4. Must be valid date/time format
```

### Storage
```
Stored in database as:
scheduled_time: "2025-12-30 14:30:00"
status: "scheduled"
```

---

## 📊 What Happens Behind the Scenes

### When You Schedule:

```
1. Form submitted
   ↓
2. Validate date/time
   ↓
3. Calculate time until execution
   ↓
4. Create campaign record (status: scheduled)
   ↓
5. Start background thread
   ↓
6. Thread waits until scheduled time
   ↓
7. Time reached → Send messages
   ↓
8. Update campaign status (status: completed)
```

### Background Thread:
```python
# Runs independently
# Not affected by logout
# Checks every minute
# Waits until exact time
# Then sends all messages
```

---

## 🎯 Use Cases

### 1. Business Hours Messaging
```
Schedule for: Tomorrow 9:00 AM
Why: Send when customers are active
```

### 2. Weekend Campaigns
```
Schedule for: Saturday 10:00 AM
Why: Better engagement on weekends
```

### 3. Time Zone Optimization
```
Schedule for: Specific time in recipient's timezone
Why: Maximum open rates
```

### 4. Campaign Planning
```
Schedule for: Week in advance
Why: Plan marketing calendar
```

### 5. Follow-up Messages
```
Schedule for: 3 days after first message
Why: Automated follow-up sequence
```

---

## ⚠️ Important Notes

### Messages Send Automatically
```
⚠️ Once scheduled, messages WILL be sent
⚠️ Works even if you log out
⚠️ Works even if you close browser
⚠️ Background process handles it
```

### How to Cancel
```
1. Go to home page
2. Find scheduled job in "Scheduled Jobs" section
3. Click "Cancel" button
4. Job removed from queue
```

### Server Requirements
```
✅ Flask app must be running
✅ Background scheduler active
✅ Server must be online at scheduled time
✅ If server restarts, jobs persist
```

---

## 🔍 Monitoring Scheduled Jobs

### Scheduled Jobs Section
```
┌─────────────────────────────────────────┐
│ 📅 Scheduled Jobs                       │
├─────────────────────────────────────────┤
│ Holiday Campaign                        │
│ ⏰ 2025-12-30 14:30                    │
│ 📊 50 messages                          │
│ ⏳ In 2 days, 19 hours                 │
│ [Cancel]                                │
└─────────────────────────────────────────┘
```

### Real-Time Updates
```
✓ Auto-refreshes every 10 seconds
✓ Shows countdown timer
✓ Updates status
✓ Shows message count
```

---

## 📱 Success Messages

### After Scheduling:
```
✅ Messages scheduled for 2025-12-30 14:30 
   (2 days and 19 hours from now). 
   They will be sent automatically even when 
   you're logged out.
```

### When Messages Send:
```
✅ 50 messages sent successfully
✅ Campaign completed
✅ Check analytics for results
```

---

## 🐛 Troubleshooting

### Issue: Can't select past dates
**Solution:** This is intentional! Only future dates allowed.

### Issue: "Scheduled time must be in the future"
**Solution:** 
- Check your system time
- Select a later time
- Ensure date is correct

### Issue: Job not showing in Scheduled Jobs
**Solution:**
- Refresh page
- Check if scheduling succeeded
- Look for error messages

### Issue: Messages not sent at scheduled time
**Solution:**
- Ensure server is running
- Check scheduled jobs list
- Verify time format
- Check server logs

---

## 💡 Best Practices

### 1. Test First
```
✓ Test with small CSV
✓ Schedule for near future
✓ Verify it works
✓ Then scale up
```

### 2. Time Selection
```
✓ Consider recipient timezone
✓ Choose business hours
✓ Avoid late night/early morning
✓ Weekend timing differs
```

### 3. Advance Planning
```
✓ Schedule days ahead
✓ Review message content
✓ Double-check recipient list
✓ Monitor scheduled jobs
```

### 4. Server Management
```
✓ Keep server running
✓ Monitor server health
✓ Check logs regularly
✓ Have backup plan
```

---

## 🎉 Benefits

### For You:
```
✅ Schedule and forget
✅ No need to stay online
✅ Plan campaigns in advance
✅ Better time management
```

### For Recipients:
```
✅ Messages at optimal times
✅ Better engagement
✅ Timezone-appropriate
✅ Professional delivery
```

### For Business:
```
✅ Automated marketing
✅ Consistent timing
✅ Better conversion rates
✅ Professional image
```

---

## 📝 Quick Reference

### Date Format
```
YYYY-MM-DD
Example: 2025-12-30
```

### Time Format
```
HH:MM (24-hour)
Examples:
- 09:00 (9:00 AM)
- 14:30 (2:30 PM)
- 18:45 (6:45 PM)
```

### Full DateTime
```
YYYY-MM-DD HH:MM
Example: 2025-12-30 14:30
```

---

## 🚀 Getting Started

### Quick Start:
```
1. Upload CSV with contacts
2. Select template or write message
3. Choose "Schedule Later"
4. Pick date and time
5. Click "Start Sending Messages"
6. Done! Messages scheduled.
```

### First Time:
```
1. Try scheduling for 5 minutes from now
2. Watch it in Scheduled Jobs
3. See countdown timer
4. Messages send automatically
5. Check Analytics for results
```

---

**Now you have full control over when messages are sent!** 📅✨

**Works 24/7, even when you're logged out!** 🌙☀️

**Schedule once, relax forever!** 😌🚀
