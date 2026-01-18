# Fix Analytics Page Error - Quick Guide

## Problem
Analytics page shows "Internal Server Error" after adding engagement tracking features.

## Cause
The database is missing the new engagement tracking columns.

## Solution - 3 Easy Steps:

### Step 1: Stop Flask
```bash
# In Terminal 1 (where Flask is running)
# Press Ctrl+C to stop Flask
```

### Step 2: Run Migration Script
```bash
# In the same terminal
python migrate_database.py
```

You should see:
```
✅ Migration completed successfully!
```

### Step 3: Restart Flask
```bash
python app.py
```

Now try accessing the Analytics page - it should work!

---

## Alternative: Manual Fix (If migration fails)

### Option 1: Delete and Recreate Database

⚠️ **Warning: This deletes all your data!**

```bash
# Stop Flask first (Ctrl+C)

# Delete the old database
del whatsapp_dashboard.db

# Start Flask - it will create a new database with all columns
python app.py
```

### Option 2: Add Columns Manually

Use SQLite browser or command line:

```bash
# Open SQLite
sqlite3 whatsapp_dashboard.db

# Add columns to campaigns table
ALTER TABLE campaigns ADD COLUMN delivered_count INTEGER DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN read_count INTEGER DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN replied_count INTEGER DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN clicked_count INTEGER DEFAULT 0;

# Add columns to messages table
ALTER TABLE messages ADD COLUMN delivered_at TEXT;
ALTER TABLE messages ADD COLUMN read_at TEXT;
ALTER TABLE messages ADD COLUMN replied_at TEXT;
ALTER TABLE messages ADD COLUMN clicked_at TEXT;
ALTER TABLE messages ADD COLUMN whatsapp_message_id TEXT;

# Exit
.quit
```

Then restart Flask.

---

## Verify It Works

After migration, test:

1. Start Flask: `python app.py`
2. Go to: http://localhost:5000/analytics
3. Should see analytics page with engagement metrics!

---

## What the Migration Does

Adds these columns:

**To campaigns table:**
- `delivered_count` - Count of delivered messages
- `read_count` - Count of read messages
- `replied_count` - Count of replies
- `clicked_count` - Count of button clicks

**To messages table:**
- `delivered_at` - When message was delivered
- `read_at` - When message was read
- `replied_at` - When recipient replied
- `clicked_at` - When button was clicked
- `whatsapp_message_id` - WhatsApp's message ID for tracking

---

## Check Flask Logs

If you still get an error after migration, check the Flask terminal for the actual error message.

Common errors:
- ❌ "no such column" → Migration didn't run properly
- ❌ "duplicate column" → Columns already exist (shouldn't happen)
- ❌ Other SQL error → Share the error message

---

## Quick Debug

To check if migration worked:

```bash
sqlite3 whatsapp_dashboard.db "PRAGMA table_info(campaigns);"
```

You should see `delivered_count`, `read_count`, etc. in the output.

---

## Still Having Issues?

Share the error message from Flask terminal (Terminal 1) when you try to access /analytics
