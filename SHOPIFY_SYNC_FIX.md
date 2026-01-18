# Shopify JSON Parsing Error - Fixed

## Problem
```
Error syncing customers: SyntaxError: Failed to execute 'json' on 'Response':
Unexpected end of JSON input
```

This happens when Shopify returns an empty or incomplete response.

## Root Causes
1. Empty response body from Shopify API
2. Network timeout/interruption
3. Shopify rate limiting
4. Invalid API credentials returning empty response

## Fixes Applied

### 1. Backend (utils/shopify_integration.py)
✅ Added timeout (30s) to prevent hanging requests
✅ Check for empty response before parsing JSON
✅ Better error messages showing response content
✅ Catch JSON parsing errors separately
✅ Added detailed logging for debugging

### 2. Frontend (templates/customers.html)
✅ Check response content-type before parsing
✅ Better error messages with troubleshooting hints
✅ Log errors to browser console for debugging

---

## Testing the Fix

### 1. Verify Shopify Credentials

Check your environment variables:
```
SHOPIFY_SHOP_NAME=your-store-name
SHOPIFY_ACCESS_TOKEN=shpat_xxxxx
```

**Important:**
- Shop name should be just the name (e.g., `my-store`, NOT `my-store.myshopify.com`)
- Access token must have `read_customers` permission

### 2. Test in Shopify Admin

1. Go to: `https://your-store.myshopify.com/admin/customers.json`
2. You should see JSON data with customers
3. If you get an error, check your access token permissions

### 3. Check Render Logs

After clicking "Sync Shopify Customers":
1. Go to Render Dashboard → Logs
2. Look for these messages:
   - `🔄 Fetching from: https://...`
   - `📊 Response status: 200`
   - `✅ Fetched X customers`

---

## Common Errors & Solutions

### Error: "Authentication failed"
**Solution:** Regenerate Shopify access token with correct permissions

### Error: "Store not found"
**Solution:** Use store name only, not full domain

### Error: "Empty response from Shopify"
**Solution:** 
- Check if your store has customers
- Verify API rate limits not exceeded
- Try again in a few minutes

### Error: Still getting JSON parse error
**Solution:**
1. Check Render logs for exact response
2. Verify Shopify API version (2024-01) is supported
3. Test API directly with curl:
```bash
curl -X GET "https://your-store.myshopify.com/admin/api/2024-01/customers.json?limit=1" \
  -H "X-Shopify-Access-Token: your_token"
```

---

## Deploy the Fix

```bash
git add .
git commit -m "Fix Shopify JSON parsing error"
git push
```

Wait 2-5 minutes for Render to redeploy.

---

## Verify Fix is Working

1. Go to Customers page
2. Click "Sync Shopify Customers"
3. Watch for success message
4. Check Render logs show:
   - No JSON errors
   - Customers fetched successfully
   - Synced count displayed

---

## If Error Persists

Share these details:
1. **Render logs** (last 50 lines when sync fails)
2. **Browser console** (F12 → Console tab)
3. **Shopify API test** result (curl command above)

This will help diagnose the specific issue with your Shopify setup.
