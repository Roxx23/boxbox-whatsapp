# Memory Optimization for Render.com Free Tier

## Problem
Render free tier has 512MB RAM limit. Your app was using 2 workers which caused memory issues.

## Solutions Applied

### 1. Optimized Gunicorn Configuration
- **Changed from 2 workers to 1 worker** - Saves ~200MB
- **Using threads (2) instead of workers** - More memory efficient
- **Increased timeout to 300s** - Prevents premature worker kills
- **Added preload_app** - Loads app once, shared across threads
- **Added max_requests** - Restarts worker periodically to prevent memory leaks

### 2. Removed Unnecessary Imports
- Removed `pandas` import from `app.py` (only imported where needed)
- Reduces initial memory footprint

### 3. Configuration File
Created `gunicorn_config.py` for better control over memory usage.

---

## If Still Getting Errors

### Option 1: Reduce Background Workers
In Render environment variables, add:
```
MESSAGE_QUEUE_WORKERS=1
```

### Option 2: Disable NumPy/Pandas Heavy Operations
If you're doing heavy data processing, consider:
- Processing data in smaller chunks
- Using database queries instead of loading everything into memory
- Caching results

### Option 3: Upgrade Render Plan
- **Starter Plan**: $7/month, 512MB RAM (but no sleep)
- **Standard Plan**: $25/month, 2GB RAM

### Option 4: Switch to Railway.app
- Better free tier: More memory, $5 credit/month
- Deploy URL: https://railway.app

---

## Monitoring Memory Usage

Add this to check memory in logs:
```python
import psutil
process = psutil.Process()
memory_mb = process.memory_info().rss / 1024 / 1024
logger.info(f"Memory usage: {memory_mb:.2f} MB")
```

---

## Current Configuration

**Procfile:**
```
web: gunicorn app:app --config gunicorn_config.py
```

**Gunicorn:**
- 1 worker
- 2 threads per worker
- 300s timeout
- Preload app
- Auto-restart after 1000 requests

This should keep memory under 400MB, leaving headroom for spikes.

---

## Deploy Changes

```bash
git add .
git commit -m "Optimize for Render free tier memory limits"
git push
```

Render will auto-deploy. Check logs to verify no more SIGKILL errors.
