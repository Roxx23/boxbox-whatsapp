# Shopify Customer Sync - Troubleshooting Guide

## Issue: Successfully synced 0 customers

This happens when the Shopify API returns customers but none of them meet the sync criteria. Here are the common causes and solutions:

### 1. **Customers Don't Have Phone Numbers** ⚠️

**Most Common Issue**: The sync only imports customers that have phone numbers (required for WhatsApp messaging).

**Solution:**
- Go to your Shopify Admin: `https://YOUR-STORE.myshopify.com/admin/customers`
- Check if your customers have phone numbers added
- Add phone numbers to customer profiles in Shopify
- Re-run the sync

**Note:** The updated code now shows you how many customers were skipped due to missing phone numbers.

### 2. **Shopify Credentials Not Configured**

Check your `.env` file has these settings:

```env
SHOPIFY_SHOP_NAME=your-store-name
SHOPIFY_ACCESS_TOKEN=shpat_xxxxxxxxxxxxx
```

**Important:**
- `SHOPIFY_SHOP_NAME` should be just the store name, NOT the full URL
  - ✅ Correct: `my-store`
  - ❌ Wrong: `my-store.myshopify.com`
  - ❌ Wrong: `https://my-store.myshopify.com`

- `SHOPIFY_ACCESS_TOKEN` should start with `shpat_` or `shpca_`

### 3. **No Customers in Shopify Store**

If your Shopify store has no customers yet:
- Add test customers in Shopify Admin
- Make sure they have phone numbers
- Then run the sync

### 4. **API Version Issues**

The integration uses Shopify API version `2024-01`. If you're using a newer API version in your Shopify app settings, you may need to update the version in the code.

To change API version:
1. Open `utils/shopify_integration.py`
2. Find line 13: `self.base_url = f"https://{shop_name}.myshopify.com/admin/api/2024-01"`
3. Change `2024-01` to your API version (e.g., `2024-10`)

### 5. **Authentication Issues**

If you get authentication errors:
- Verify your Access Token is valid
- Check that your Shopify app has the correct permissions:
  - `read_customers`
  - `read_orders` (optional, for order history)
- Regenerate the token if needed

### 6. **Testing the Connection**

Run the debug script to test your Shopify connection:

```bash
python debug_shopify.py
```

This will:
- Verify your credentials
- Test API connectivity
- Show how many customers exist in your store
- Display first customer details
- Identify if customers have phone numbers

### 7. **Check Application Logs**

After the update, the sync endpoint now logs detailed information:

**What to look for in logs:**
- ✅ "Fetched X customers from Shopify" - Shows total customers fetched
- ⚠️ "Skipped customer (no phone)" - Shows which customers were skipped
- ❌ Any error messages

**How to view logs:**
- Check the terminal where your Flask app is running
- Look for emoji indicators: 🔄 ✅ ⚠️ ❌

### Updated Features (Applied)

The sync endpoint now provides:

1. **Detailed logging**: See exactly what's happening during sync
2. **Skip tracking**: Know how many customers were skipped and why
3. **Enhanced response**: Shows:
   - `synced_count`: Customers successfully synced
   - `skipped_count`: Customers skipped (no phone number)
   - `total_fetched`: Total customers fetched from Shopify

4. **Better error messages**: More informative alerts

### Example Scenarios

**Scenario 1: All customers synced**
```
✅ Successfully synced 25 customers from Shopify
```

**Scenario 2: Some customers skipped**
```
✅ Successfully synced 15 customers from Shopify (10 customers skipped - no phone number)
```

**Scenario 3: No customers with phone numbers**
```
✅ Successfully synced 0 customers from Shopify (25 customers skipped - no phone number)
```
This means you have 25 customers but none have phone numbers!

**Scenario 4: Credentials not configured**
```
❌ Error: Shopify credentials not configured. Please add SHOPIFY_SHOP_NAME and SHOPIFY_ACCESS_TOKEN to your .env file
```

### Quick Fix Steps

1. **Restart your Flask application** to load the updated code
2. **Check your .env file** has correct Shopify credentials
3. **Run the sync** from the Customers page
4. **Check the logs** in your terminal for detailed information
5. **Add phone numbers** to customers in Shopify if needed
6. **Run sync again**

### Getting Shopify Credentials

If you don't have Shopify credentials yet:

1. Go to your Shopify Admin
2. Navigate to **Settings** → **Apps and sales channels**
3. Click **Develop apps**
4. Create a new app or select existing one
5. Configure **Admin API scopes**: Enable `read_customers`
6. Install the app to your store
7. Get the **Admin API access token** (starts with `shpat_`)
8. Your **store name** is in your Shopify URL: `https://YOUR-STORE.myshopify.com/admin`

### Need More Help?

If sync still shows 0 customers:

1. Run `python debug_shopify.py` and share the output
2. Check the terminal logs when clicking sync
3. Verify customers in Shopify Admin have phone numbers
4. Make sure phone numbers are in international format (e.g., +1234567890)

## Phone Number Format

The integration automatically formats phone numbers:
- Removes spaces, dashes, parentheses
- Adds + prefix if missing
- Example: `(555) 123-4567` → `+5551234567`

However, customers **must have a phone number entered** in Shopify for this to work.
