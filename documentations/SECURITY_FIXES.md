# WhatsApp Dashboard - Security & Bug Fixes

## Recent Updates (December 2025)

### 🔴 **Critical Security Fixes**

#### 1. **Secret Key Security**
- ❌ **Before:** Hardcoded default secret key (`'change-this-in-production'`)
- ✅ **After:** Secret key must be set in `.env` file, app will not start without it
- **Why:** Prevents session hijacking and ensures secure production deployment

#### 2. **Debug Mode in Production**
- ❌ **Before:** `debug=True` and exposed to all network interfaces (`0.0.0.0`)
- ✅ **After:** Debug mode controlled by `FLASK_DEBUG` env var, defaults to `False`
- ✅ **After:** Host controlled by `FLASK_HOST` env var, defaults to `127.0.0.1`
- **Why:** Debug mode exposes sensitive information and allows code execution

#### 3. **Environment Variable Validation**
- ❌ **Before:** App would start with missing credentials
- ✅ **After:** App validates all required env vars on startup and fails fast with clear error
- **Required vars:** `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WABA_ID`, `SECRET_KEY`

### 🟡 **Medium Priority Fixes**

#### 4. **Phone Number Validation**
- ✅ Added validation for phone numbers in CSV uploads
- ✅ Checks for valid length (10-15 digits)
- ✅ Shows specific invalid phone numbers to user

#### 5. **CSV Encoding Handling**
- ✅ Added UTF-8 encoding support with latin-1 fallback
- ✅ Prevents crashes with non-UTF-8 CSV files

#### 6. **Empty DataFrame Check**
- ✅ Now validates that CSV is not empty before processing
- ✅ Shows user-friendly error message

#### 7. **CSV File Extension Validation**
- ✅ Validates `.csv` extension before processing
- ✅ Prevents issues with Excel files being uploaded

#### 8. **Configurable Rate Limiting**
- ✅ Rate limits now configurable via environment variables
- **Env vars:** `RATE_LIMIT_REQUESTS`, `RATE_LIMIT_WINDOW`, `MESSAGE_QUEUE_WORKERS`
- **Why:** Different WhatsApp API tiers have different limits

#### 9. **Thread-Safe Job Management**
- ✅ Added threading locks for scheduled job modifications
- ✅ Prevents race conditions in job cancellation

#### 10. **Hardcoded WABA_ID Fixed**
- ❌ **Before:** `background_scheduler.py` had hardcoded WABA_ID
- ✅ **After:** WABA_ID passed from app.py via `set_waba_id()` function

### 🟢 **Code Quality Improvements**

#### 11. **Structured Logging**
- ✅ Replaced `print()` statements with Python's `logging` module
- ✅ Consistent log format with timestamps
- ✅ Proper log levels (INFO, WARNING, ERROR)

#### 12. **Removed Debug Output**
- ✅ Removed excessive debug print statements from production code
- ✅ Cleaned up template submission debug logs

---

## Setup Instructions

### 1. **Configure Environment Variables**

```bash
# Copy example file
cp .env.example .env

# Edit .env file with your credentials
nano .env  # or use your favorite editor
```

### 2. **Generate Secure Secret Key**

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output and paste it as `SECRET_KEY` in your `.env` file.

### 3. **Required Environment Variables**

```env
# WhatsApp API Credentials (Required)
WHATSAPP_ACCESS_TOKEN=EAAxxxxxxxxxxxx
WHATSAPP_PHONE_NUMBER_ID=123456789
WABA_ID=123456789

# Security (Required)
SECRET_KEY=your_generated_secret_key_here

# Server Configuration (Optional)
FLASK_DEBUG=False
FLASK_HOST=127.0.0.1
FLASK_PORT=5000

# Rate Limiting (Optional)
RATE_LIMIT_REQUESTS=20
RATE_LIMIT_WINDOW=1.0
MESSAGE_QUEUE_WORKERS=1
```

### 4. **Install Dependencies**

```bash
pip install -r requirements.txt
```

### 5. **Run Application**

```bash
python app.py
```

---

## Production Deployment Checklist

- [ ] Set `FLASK_DEBUG=False` in production
- [ ] Use strong `SECRET_KEY` (32+ characters, randomly generated)
- [ ] Set `FLASK_HOST=127.0.0.1` (use reverse proxy like nginx for external access)
- [ ] Configure rate limits based on your WhatsApp API tier
- [ ] Keep `.env` file secure and never commit to git
- [ ] Use HTTPS for all external connections
- [ ] Monitor logs for suspicious activity
- [ ] Set up proper error handling and alerting

---

## CSV Upload Requirements

### Required Columns
- `Phone` - Phone number column (required)

### Phone Number Format
- Must be 10-15 digits
- Can include country code
- Special characters (spaces, dashes, parentheses) will be removed automatically
- Invalid formats will be rejected with specific error messages

### Example CSV

```csv
Phone,Name,Email
+919876543210,John Doe,john@example.com
919876543211,Jane Smith,jane@example.com
9876543212,Bob Johnson,bob@example.com
```

---

## Rate Limiting Configuration

### WhatsApp API Limits
- **Standard:** 80 messages/second
- **Cloud API (approved):** 1000 messages/second
- **Recommended:** 20-50 messages/second for safety

### Configuration

Adjust in `.env`:
```env
RATE_LIMIT_REQUESTS=20    # Max requests per time window
RATE_LIMIT_WINDOW=1.0     # Time window in seconds
MESSAGE_QUEUE_WORKERS=1   # Number of worker threads
```

---

## Troubleshooting

### "Missing required environment variables" Error
- Check that all required vars are set in `.env` file
- Make sure `.env` file is in the root directory
- Verify no typos in variable names

### "Invalid phone number" Errors
- Check CSV for phone numbers with invalid format
- Error message will show which rows have invalid numbers
- Ensure phone numbers are 10-15 digits

### Rate Limiting Issues
- Adjust `RATE_LIMIT_REQUESTS` and `RATE_LIMIT_WINDOW` in `.env`
- Check your WhatsApp API tier limits
- Monitor queue status at `/queue-status`

---

## Security Best Practices

1. **Never commit `.env` file** - Already in `.gitignore`
2. **Rotate credentials regularly** - Change access tokens periodically
3. **Use HTTPS** - Always use secure connections in production
4. **Monitor logs** - Check for unauthorized access attempts
5. **Limit file uploads** - Current limit: 5MB (already implemented)
6. **Validate all inputs** - Phone numbers, CSV data (already implemented)
7. **Use reverse proxy** - nginx or Apache for production
8. **Enable firewall** - Restrict access to necessary ports only

---

## API Endpoints

- `/` - Main dashboard
- `/create-template` - Template creation page
- `/submit-template` - Template submission (POST)
- `/queue-status` - Message queue monitoring
- `/queue-stats` - Queue statistics (JSON)
- `/scheduled-jobs` - View scheduled jobs
- `/cancel-job/<job_id>` - Cancel a scheduled job

---

## Support

For issues or questions:
1. Check logs in console output
2. Verify `.env` configuration
3. Check WhatsApp API status
4. Review error messages carefully

---

## License

[Your License Here]

---

## Changelog

### v2.0.0 (December 2025)
- 🔴 Fixed critical security vulnerabilities
- 🟡 Added input validation and error handling
- 🟢 Improved code quality and logging
- ✅ Added comprehensive documentation
- ✅ Thread-safe job management
- ✅ Configurable rate limiting
- ✅ Environment variable validation
