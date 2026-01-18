# 🔧 Dashboard Troubleshooting Guide

## ❓ What's Not Working?

Please provide more details:

1. **What error do you see?**
   - Blank page?
   - Error message?
   - Page won't load?
   - JavaScript errors in browser console?

2. **Where does it fail?**
   - Can't start the app (`python app.py`)?
   - App starts but browser shows error?
   - Page loads but features don't work?

---

## 🧪 Quick Diagnostics

### Test 1: Check if app starts
```bash
python test_imports.py
```

**Expected output:**
```
✅ utils.whatsapp imported successfully
✅ Set for all config values
✅ Flask imported successfully
✅ Database initialized successfully
✅ templates/index.html exists
```

### Test 2: Start the app
```bash
python app.py
```

**Expected output:**
```
 * Running on http://127.0.0.1:5000
 * Running on http://192.168.x.x:5000
```

If you see errors, **copy and paste them here**.

### Test 3: Check browser console
1. Open browser to `http://localhost:5000`
2. Press `F12` to open Developer Tools
3. Go to **Console** tab
4. Look for any red error messages

Common errors:
- `Uncaught SyntaxError` → JavaScript syntax error
- `Failed to fetch` → Backend not responding
- `404 Not Found` → File missing

---

## 🔍 Common Issues

### Issue 1: "ModuleNotFoundError"
**Error**: `ModuleNotFoundError: No module named 'X'`

**Fix**:
```bash
pip install -r requirements.txt
```

### Issue 2: "Address already in use"
**Error**: Port 5000 is already in use

**Fix**:
```bash
# Kill existing Flask process
# Windows:
taskkill /F /IM python.exe

# Linux/Mac:
pkill python
```

### Issue 3: ".env file not found"
**Error**: Config values missing

**Fix**: Make sure `.env` file exists with:
```env
WHATSAPP_ACCESS_TOKEN=your_token
WHATSAPP_PHONE_NUMBER_ID=your_phone_id
WABA_ID=your_waba_id
SECRET_KEY=your_secret_key
```

### Issue 4: "Template syntax error"
**Error**: Jinja2 template error

**Fix**: Check if `templates/index.html` has syntax errors

Look for:
- Unclosed `<div>` tags
- Missing `{% endfor %}` or `{% endif %}`
- JavaScript errors (missing `;` or `}`)

### Issue 5: "JavaScript not working"
**Symptoms**: Buttons don't respond, dropdowns don't populate

**Fix**:
1. Clear browser cache (Ctrl+Shift+Delete)
2. Hard refresh (Ctrl+F5 or Cmd+Shift+R)
3. Check browser console for errors (F12)

---

## 🛠️ Fixes Applied Recently

### Fixed in templates/index.html:
- ✅ Removed duplicate `});` closing brace (line 1053)
- ✅ Added button parameter fields
- ✅ Added requirements banner

### Fixed in utils/whatsapp.py:
- ✅ Changed to load from environment instead of config
- ✅ Added button index auto-detection
- ✅ Added WABA_ID loading

---

## 📋 Verification Checklist

Run through these to identify the issue:

- [ ] `.env` file exists with all required variables
- [ ] `python test_imports.py` runs without errors
- [ ] `python app.py` starts without errors
- [ ] Browser can access `http://localhost:5000`
- [ ] Browser console (F12) shows no red errors
- [ ] Can see login page or dashboard home
- [ ] Can upload CSV file
- [ ] Can select template
- [ ] Parameter fields appear when template selected

**Which step fails?** Let me know and I'll help fix it.

---

## 🚨 Emergency Rollback

If nothing works, restore the previous version:

### Option 1: Revert templates/index.html
```bash
# Backup current version
cp templates/index.html templates/index.html.new

# Restore from git (if using git)
git checkout templates/index.html
```

### Option 2: Revert utils/whatsapp.py
```bash
# Restore original imports
# Edit utils/whatsapp.py line 1-11:
```
```python
import requests
import time
import re
from config import ACCESS_TOKEN, PHONE_NUMBER_ID

# Add at top of file after imports:
import os
from dotenv import load_dotenv
load_dotenv()
WABA_ID = os.getenv("WABA_ID")
```

---

## 📞 Get Help

To help diagnose:

1. Run: `python test_imports.py`
2. Try: `python app.py`
3. Copy any error messages
4. Check browser console (F12 → Console tab)
5. Share the errors you see

**Most common issue**: JavaScript syntax error from the edit. Already fixed by removing duplicate `});`

**Try now**: 
```bash
python app.py
```

Then open `http://localhost:5000` and let me know what you see!
