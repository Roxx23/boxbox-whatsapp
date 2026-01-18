# 🚀 Quick Start Guide

Get your WhatsApp Dashboard running in 5 minutes!

---

## Prerequisites

- Python 3.7+
- pip package manager
- WhatsApp Business API credentials

---

## Step 1: Clone/Download (if needed)

```bash
git clone <your-repo-url>
cd whatsapp-dashboard
```

---

## Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Step 3: Run Setup Script

```bash
python setup.py
```

This will:
- ✅ Create `.env` file
- ✅ Generate secure SECRET_KEY
- ✅ Validate dependencies

---

## Step 4: Configure Your API Credentials

Edit `.env` file:

```env
# Required - Get from https://business.facebook.com/
WHATSAPP_ACCESS_TOKEN=your_token_here
WHATSAPP_PHONE_NUMBER_ID=your_phone_id_here
WABA_ID=your_waba_id_here

# Auto-generated - Don't change
SECRET_KEY=<already_set>
```

### Where to Find Your Credentials:

1. Go to [Meta Business Suite](https://business.facebook.com/)
2. Select your app
3. Go to WhatsApp > API Setup
4. Copy:
   - Access Token → `WHATSAPP_ACCESS_TOKEN`
   - Phone Number ID → `WHATSAPP_PHONE_NUMBER_ID`
   - WhatsApp Business Account ID → `WABA_ID`

---

## Step 5: Start the Application

```bash
python app.py
```

You should see:
```
✅ Message queue started successfully
====================================================
🚀 Starting WhatsApp Bulk Sender
🌐 Host: 127.0.0.1:5000
====================================================
```

---

## Step 6: Open in Browser

Navigate to: **http://127.0.0.1:5000**

---

## ✅ You're Ready!

Now you can:
- 📤 Upload CSV files with contacts
- 📱 Send bulk WhatsApp messages
- 📝 Create message templates
- ⏰ Schedule messages for later
- 📊 Monitor message queue

---

## 📋 CSV Format

Your CSV file should look like:

```csv
Phone,Name,Email
+919876543210,John Doe,john@example.com
919876543211,Jane Smith,jane@example.com
9876543212,Bob Johnson,bob@example.com
```

**Required column:** `Phone`  
**Optional columns:** Any others you want for personalization

---

## 🆘 Troubleshooting

### "Missing required environment variables"
→ Run `python setup.py` and fill in your credentials in `.env`

### "Invalid phone number"
→ Check your CSV - phone numbers must be 10-15 digits

### "CSV file is empty"
→ Make sure your CSV has data rows (not just headers)

### App won't start
→ Make sure you ran `pip install -r requirements.txt`

---

## 📖 Next Steps

- Read `SECURITY_FIXES.md` for production deployment
- Check `MIGRATION_GUIDE.md` if upgrading from old version
- Review `ALL_FIXES_SUMMARY.md` for all features

---

## 🔐 Security Reminder

- ⚠️ Never commit `.env` file to git
- ⚠️ Keep your API credentials secret
- ⚠️ Use strong SECRET_KEY (auto-generated)
- ⚠️ Set `FLASK_DEBUG=False` in production

---

## 🎉 That's It!

You're all set to send bulk WhatsApp messages!

For help: Check the documentation files in the project root.
