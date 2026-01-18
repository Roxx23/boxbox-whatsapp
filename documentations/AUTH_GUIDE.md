# 🔐 Authentication System Guide

## Overview
Your WhatsApp Dashboard now has a complete login/signup authentication system!

---

## ✨ Features

### User Authentication
- ✅ **Secure Registration** - Password hashing with bcrypt
- ✅ **Login/Logout** - Session-based authentication
- ✅ **Remember Me** - Option to stay logged in
- ✅ **Protected Routes** - All dashboard features require login

### Security Features
- 🔒 **Password Hashing** - Bcrypt encryption
- 🔒 **Session Management** - Flask-Login integration
- 🔒 **CSRF Protection** - Built into Flask forms
- 🔒 **Input Validation** - Client and server-side validation

---

## 🚀 Installation

### 1. Install New Dependencies

```bash
pip install flask-login bcrypt
```

Or install from the new requirements file:
```bash
pip install -r requirements_new.txt
```

### 2. Restart Your Application

```bash
python app.py
```

---

## 📋 How to Use

### First Time Setup

1. **Start the application:**
   ```bash
   python app.py
   ```

2. **Open your browser:**
   ```
   http://127.0.0.1:5000
   ```

3. **You'll be redirected to the login page**

4. **Click "Sign up here" to create your first account**

5. **Fill in the registration form:**
   - Username: 3-20 characters, letters/numbers only
   - Email: Valid email address
   - Password: At least 8 characters with:
     - One uppercase letter
     - One lowercase letter
     - One number
  
6. **After signup, login with your credentials**

---

## 🎯 Features Explained

### Registration Page (`/signup`)

**Password Requirements:**
- ✅ Minimum 8 characters
- ✅ At least one uppercase letter (A-Z)
- ✅ At least one lowercase letter (a-z)
- ✅ At least one number (0-9)

**Real-time Validation:**
- Live password strength indicator
- Shows which requirements are met
- Confirms password match

**Username Rules:**
- 3-20 characters
- Letters and numbers only
- Must be unique

### Login Page (`/login`)

**Features:**
- Login with username OR email
- "Remember me" checkbox for persistent sessions
- Password visibility toggle
- Redirects to intended page after login

### Protected Dashboard

All these routes now require login:
- `/` - Main dashboard
- `/create-template` - Template creation
- `/queue-status` - Queue monitoring
- `/scheduled-jobs` - Job management
- All API endpoints

---

## 🔧 Technical Details

### File Structure

```
utils/
  └── auth.py              # User authentication logic

templates/
  ├── login.html           # Login page
  └── signup.html          # Signup page

users.json                  # User database (auto-created)
```

### User Data Storage

Users are stored in `users.json`:
```json
{
  "1": {
    "id": "1",
    "username": "admin",
    "email": "admin@example.com",
    "password_hash": "hashed_password_here",
    "created_at": "2025-12-26T19:50:00"
  }
}
```

⚠️ **Security Note:** `users.json` is added to `.gitignore` automatically

### Password Hashing

Passwords are hashed using **bcrypt**:
- Industry-standard encryption
- Salt automatically generated
- One-way hashing (cannot be decrypted)
- Resistant to rainbow table attacks

---

## 🛡️ Security Best Practices

### What's Protected:
1. ✅ Passwords encrypted with bcrypt
2. ✅ Sessions secured with SECRET_KEY
3. ✅ All routes protected with @login_required
4. ✅ User data not committed to git
5. ✅ Input validation on registration

### Additional Recommendations:
- 🔒 Use HTTPS in production
- 🔒 Set secure session cookies
- 🔒 Implement rate limiting on login
- 🔒 Add email verification (future enhancement)
- 🔒 Add password reset (future enhancement)

---

## 📊 User Management

### Check User Count

Users are stored in `users.json`. To view:
```python
from utils.auth import UserManager
um = UserManager()
print(f"Total users: {um.user_count()}")
```

### Create Admin User Programmatically

```python
from utils.auth import UserManager

um = UserManager()
user, error = um.create_user(
    username="admin",
    email="admin@example.com",
    password="Admin123"
)

if user:
    print("Admin user created!")
else:
    print(f"Error: {error}")
```

---

## 🔄 Migration for Existing Users

If you already have the app running, you'll need to:

1. **Install new dependencies:**
   ```bash
   pip install flask-login bcrypt
   ```

2. **Restart the application:**
   ```bash
   python app.py
   ```

3. **Create your first user account**
   - Visit `/signup`
   - Register a new account
   - Login and continue using the dashboard

---

## 🎨 UI/UX Features

### Modern Design
- 🎨 Gradient background
- 🎨 Smooth animations
- 🎨 Responsive layout
- 🎨 Mobile-friendly

### User-Friendly
- 👁️ Password visibility toggle
- ✅ Real-time validation
- 📝 Clear error messages
- 🔄 Smooth redirects

---

## 🐛 Troubleshooting

### "Please install flask-login"

**Solution:**
```bash
pip install flask-login bcrypt
```

### "Username already exists"

**Solution:**
- Choose a different username
- Or delete `users.json` to reset (⚠️ removes all users)

### Can't Access Dashboard

**Solution:**
- Make sure you're logged in
- Check if you're redirected to `/login`
- Clear browser cookies if stuck

### Forgot Password

**Currently:** No password reset feature (coming soon)

**Workaround:**
1. Stop the application
2. Delete or edit `users.json`
3. Create a new account

---

## 🔜 Future Enhancements

### Planned Features:
- [ ] Email verification
- [ ] Password reset via email
- [ ] Two-factor authentication (2FA)
- [ ] User roles (Admin, User, etc.)
- [ ] Activity logging
- [ ] Account settings page
- [ ] Profile management
- [ ] Password change
- [ ] Account deletion

---

## 🧪 Testing

### Test Registration:
1. Go to `/signup`
2. Enter test credentials
3. Submit form
4. Should redirect to login

### Test Login:
1. Go to `/login`
2. Enter credentials
3. Check "Remember me"
4. Should redirect to dashboard

### Test Protection:
1. Logout
2. Try accessing `/`
3. Should redirect to login

---

## 📖 API Reference

### UserManager Class

```python
from utils.auth import UserManager

um = UserManager()

# Create user
user, error = um.create_user(username, email, password)

# Authenticate
user = um.authenticate(username, password)

# Get user by ID
user = um.get_user_by_id(user_id)

# Get user by username
user = um.get_user_by_username(username)

# Get all users
users = um.get_all_users()

# Get user count
count = um.user_count()
```

### User Object

```python
user.id              # User ID
user.username        # Username
user.email           # Email address
user.password_hash   # Hashed password
user.created_at      # Registration timestamp
user.check_password(password)  # Verify password
```

---

## ✅ Checklist

After installation, verify:

- [ ] Flask-login and bcrypt installed
- [ ] Application starts without errors
- [ ] Redirects to `/login` when accessing `/`
- [ ] Can create new account at `/signup`
- [ ] Can login with credentials
- [ ] Dashboard accessible after login
- [ ] Can logout successfully
- [ ] `users.json` created automatically
- [ ] `users.json` in `.gitignore`

---

## 🎉 You're All Set!

Your WhatsApp Dashboard now has secure authentication!

**Next Steps:**
1. Create your admin account
2. Login and use the dashboard
3. Optionally customize the login/signup pages
4. Consider adding the planned enhancements

---

**Version:** 2.1.0  
**Added:** December 26, 2025  
**Status:** ✅ Fully Functional
