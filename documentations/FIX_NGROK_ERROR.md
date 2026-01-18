# Fix Ngrok "Command Not Found" Error

## Problem
You get this error:
```
ngrok : The term 'ngrok' is not recognized...
```

Even though you installed ngrok and added it to PATH.

---

## Quick Fixes (Try These in Order)

### ✅ Fix 1: Restart PowerShell/CMD (Most Common)

After adding to environment variables, you MUST restart your terminal!

1. **Close all PowerShell/CMD windows**
2. **Open a NEW PowerShell/CMD window**
3. **Try again:**
   ```bash
   ngrok http 5000
   ```

**Why this works:** Windows only reads environment variables when terminal starts

---

### ✅ Fix 2: Use Full Path (Temporary Quick Fix)

Instead of just `ngrok`, use the full path:

```bash
C:\ngrok\ngrok.exe http 5000
```

Or wherever you installed it:
```bash
C:\Users\YourName\Downloads\ngrok.exe http 5000
```

---

### ✅ Fix 3: Add to PATH Correctly

Let me help you add ngrok to PATH properly:

#### Step-by-Step:

**1. Find where ngrok.exe is located**

Common locations:
- `C:\ngrok\`
- `C:\Program Files\ngrok\`
- `C:\Users\YourName\Downloads\`

**2. Copy the folder path** (NOT the .exe file, just the folder)

Example: `C:\ngrok`

**3. Add to PATH:**

**Method A: Using Windows Settings**

1. Press `Windows + R`
2. Type: `sysdm.cpl` and press Enter
3. Click "Advanced" tab
4. Click "Environment Variables"
5. Under "System variables", find "Path"
6. Click "Edit"
7. Click "New"
8. Paste: `C:\ngrok` (your ngrok folder)
9. Click "OK" on all windows
10. **RESTART PowerShell/CMD**

**Method B: Using PowerShell (as Administrator)**

```powershell
# Run PowerShell as Administrator
# Right-click PowerShell -> Run as Administrator

# Add to User PATH (recommended)
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\ngrok", "User")

# Restart PowerShell after this!
```

**Method C: Using CMD (as Administrator)**

```cmd
setx PATH "%PATH%;C:\ngrok"
```

---

### ✅ Fix 4: Verify PATH Addition

Check if ngrok is in PATH:

**In CMD:**
```cmd
echo %PATH%
```

**In PowerShell:**
```powershell
$env:PATH -split ';' | Select-String ngrok
```

**Look for:** `C:\ngrok` or wherever you installed it

---

### ✅ Fix 5: Move ngrok.exe to System Folder (Easy Alternative)

Instead of messing with PATH, just move ngrok to a folder that's already in PATH:

**Option 1: Move to Windows folder**
```cmd
# In CMD as Administrator
copy C:\ngrok\ngrok.exe C:\Windows\System32\
```

**Option 2: Move to a common location**
```cmd
# Create a folder
mkdir C:\bin

# Move ngrok there
copy C:\ngrok\ngrok.exe C:\bin\

# Add C:\bin to PATH (see Fix 3 above)
```

---

## ✅ Fix 6: Use Relative Path

If ngrok is in your project folder:

```bash
# If ngrok.exe is in your current directory
.\ngrok.exe http 5000
```

---

## ✅ Complete Setup Example

Here's the FULL process from scratch:

### Step 1: Download ngrok

1. Go to: https://ngrok.com/download
2. Download Windows version (zip file)
3. Extract the zip file

### Step 2: Move ngrok to a permanent location

```cmd
# Create a folder
mkdir C:\tools\ngrok

# Move ngrok.exe there
# (Manually move the file or use copy command)
```

### Step 3: Add to PATH

**Using Windows Settings:**
1. Search for "Environment Variables" in Start Menu
2. Click "Edit the system environment variables"
3. Click "Environment Variables" button
4. Under "User variables", select "Path"
5. Click "Edit"
6. Click "New"
7. Type: `C:\tools\ngrok`
8. Click OK on everything
9. **Restart terminal!**

### Step 4: Test

```bash
# Close and reopen PowerShell/CMD
ngrok --version
```

Should show: `ngrok version 3.x.x`

---

## Alternative: Use Without PATH

Don't want to mess with PATH? Just use full path every time:

**Create a script:**

Create `start_ngrok.bat` in your project folder:
```batch
@echo off
C:\ngrok\ngrok.exe http 5000
pause
```

Then just double-click the .bat file!

---

## Still Not Working?

### Debug Steps:

**1. Verify ngrok.exe exists:**
```cmd
dir C:\ngrok\ngrok.exe
```

Should show the file. If not, you need to find where it actually is.

**2. Check if it's the .exe file:**

Make sure it's `ngrok.exe`, not just `ngrok`

**3. Try running directly:**
```cmd
C:\ngrok\ngrok.exe --version
```

If this works, the problem is PATH. If not, the file might be corrupted.

**4. Re-download ngrok:**

Sometimes the download gets corrupted. Download fresh from:
https://ngrok.com/download

**5. Check Windows Defender:**

Sometimes antivirus blocks it. Check:
- Windows Security → Virus & threat protection → Protection history

**6. Run as Administrator:**

Right-click PowerShell → Run as Administrator
```powershell
C:\ngrok\ngrok.exe http 5000
```

---

## Quick Workaround for NOW

If you need to test webhooks RIGHT NOW and ngrok is being difficult:

### Use Localtunnel Instead:

```bash
# Install
npm install -g localtunnel

# Use (no PATH issues!)
npx localtunnel --port 5000
```

Or use the full path method:

```bash
# Terminal 1: Start Flask
python app.py

# Terminal 2: Start ngrok with full path
C:\ngrok\ngrok.exe http 5000
```

---

## For Your Specific Case

Since you installed in `C:\` drive, try:

**Option 1: Full path**
```cmd
C:\ngrok\ngrok.exe http 5000
```

**Option 2: Check exact location**
```cmd
# Search for ngrok.exe
where /R C:\ ngrok.exe
```

This will show you EXACTLY where it is.

**Option 3: Add correct path**

Once you know the exact folder, add THAT to PATH:
```powershell
# If ngrok.exe is at C:\ngrok\ngrok.exe
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\ngrok", "User")

# Restart PowerShell after!
```

---

## The Most Common Mistake

❌ **Added PATH but didn't restart terminal**

You MUST close and reopen PowerShell/CMD after changing PATH!

✅ **Correct Process:**
1. Add to PATH
2. Click OK on all windows
3. **Close PowerShell/CMD completely**
4. **Open NEW PowerShell/CMD**
5. Test: `ngrok --version`

---

## Summary: Three Ways to Run Ngrok

### Way 1: Add to PATH (Permanent)
```bash
# After adding C:\ngrok to PATH and restarting
ngrok http 5000
```

### Way 2: Use Full Path (Works Always)
```bash
C:\ngrok\ngrok.exe http 5000
```

### Way 3: Use Batch File (Easy)
Create `start_ngrok.bat`:
```batch
@echo off
cd /d C:\ngrok
ngrok.exe http 5000
pause
```

Double-click to run!

---

**Need more help?** 

Share the output of:
```cmd
where /R C:\ ngrok.exe
```

This will tell us EXACTLY where ngrok is, and I can give you the exact command to use!
