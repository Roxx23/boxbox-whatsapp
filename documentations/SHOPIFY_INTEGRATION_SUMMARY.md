# Shopify Integration - Changes Summary

## Overview
Successfully integrated Shopify customer management with automatic segmentation and targeted messaging capabilities.

## Files Created

### 1. `utils/shopify_integration.py`
- ShopifyIntegration class for API communication
- Methods to fetch customers and orders
- Customer data parsing and phone number formatting

### 2. `templates/customers.html`
- Customer management interface
- Segment filtering UI
- Customer selection for bulk messaging
- Sync Shopify button
- Engagement metrics display

### 3. `SHOPIFY_INTEGRATION_GUIDE.md`
- Complete setup instructions
- API documentation
- Troubleshooting guide
- Best practices

## Files Modified

### 1. `config.py`
Added Shopify configuration:
```python
SHOPIFY_SHOP_NAME = os.getenv("SHOPIFY_SHOP_NAME")
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")
```

### 2. `utils/database.py`
Added:
- **customers table**: Store Shopify customer data with engagement tracking
- **customer_segments table**: Store custom segments
- Methods:
  - `add_or_update_customer()` - Import/update customers
  - `get_all_customers()` - Retrieve customers with filters
  - `get_customer_by_phone()` - Find customer by phone
  - `update_customer_message_stats()` - Track sent/read/replied metrics
  - `create_segment()` - Create custom segments
  - `get_user_segments()` - Get user's segments
  - `get_segment_customers()` - Get customers in segment

### 3. `app.py`
Added routes:
- `/customers` - Customer management page
- `/api/sync-shopify` - Sync customers from Shopify
- `/api/customers/<segment>` - Get customers by segment

Modified:
- `index()` route - Handle both CSV and customer selection
- `process_message_status()` - Update customer engagement stats
- `process_incoming_message()` - Track replies at customer level

### 4. `templates/index.html`
Added:
- Radio button to switch between CSV and Customer selection
- Customer selection section with session storage integration
- Navigation link to Customers page
- JavaScript functions:
  - `toggleSource()` - Switch between CSV/Customers
  - `goToCustomers()` - Navigate to customer page
  - `updateCustomerSelection()` - Load selected customers
  - Session storage handling for customer selection

### 5. `templates/campaign_details.html`
Fixed:
- Removed 100 message limit (now shows all messages)
- Changed reply button condition from `replied_at and reply_text` to just `replied_at`

## Database Schema

### customers table
```sql
CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    user_id TEXT,
    shopify_id TEXT UNIQUE,
    first_name TEXT,
    last_name TEXT,
    email TEXT,
    phone TEXT,
    total_spent REAL,
    orders_count INTEGER,
    state TEXT,
    tags TEXT,
    last_message_sent TEXT,
    last_message_read TEXT,
    last_message_replied TEXT,
    messages_sent_count INTEGER DEFAULT 0,
    messages_read_count INTEGER DEFAULT 0,
    messages_replied_count INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT
)
```

### customer_segments table
```sql
CREATE TABLE customer_segments (
    id INTEGER PRIMARY KEY,
    user_id TEXT,
    segment_name TEXT,
    segment_type TEXT,
    conditions TEXT,
    customer_count INTEGER,
    created_at TEXT,
    updated_at TEXT
)
```

## Features Implemented

### 1. Shopify Integration
✅ Automatic customer sync from Shopify
✅ Fetch customer name, phone, email, orders, spending
✅ Phone number validation and formatting
✅ Pagination support for large customer bases

### 2. Automatic Segmentation
✅ **All Customers** - Complete customer list
✅ **Has Phone Number** - Customers with valid phone numbers
✅ **Engaged (Last 7 Days)** - Customers who read messages recently
✅ **Never Messaged** - Untapped customers
✅ **High Value (>$1000)** - High-spending customers
✅ **Has Orders** - Customers with purchase history
✅ **Replied to Messages** - Engaged customers

### 3. Customer Selection
✅ Select customers from dashboard
✅ Bulk selection with checkboxes
✅ Select All functionality
✅ Session storage for seamless navigation
✅ Send messages to selected customers

### 4. Engagement Tracking
✅ Track messages sent per customer
✅ Track messages read per customer
✅ Track replies per customer
✅ Track last message date
✅ Track last read date
✅ Track last reply date
✅ Automatic webhook integration

### 5. UI Improvements
✅ Professional customer management interface
✅ Segment cards with counts
✅ Engagement metrics badges
✅ Sync button with loading state
✅ Customer count display
✅ Responsive table layout

## Setup Required

### 1. Environment Variables
Add to `.env`:
```
SHOPIFY_SHOP_NAME=your-store
SHOPIFY_ACCESS_TOKEN=shpat_xxxxxxxxxxxxx
```

### 2. Shopify App Setup
1. Create private app in Shopify
2. Enable `read_customers` and `read_orders` permissions
3. Get Admin API access token
4. Add credentials to `.env`

### 3. First Sync
1. Go to Customers page
2. Click "Sync Shopify"
3. Wait for import to complete

## Usage Flow

1. **Sync Customers**: Click "Sync Shopify" to import customers
2. **View Segments**: Browse automatic segments to find target audience
3. **Select Customers**: Check boxes for customers to message
4. **Send Messages**: Click "Send Message to Selected"
5. **Choose Template**: Select template or compose message
6. **Track Engagement**: Monitor read/reply rates per customer

## Benefits

✅ **No Manual CSV Upload**: Customers auto-synced from Shopify
✅ **Smart Segmentation**: Automatic grouping by behavior and value
✅ **Better Targeting**: Send to specific customer segments
✅ **Engagement Insights**: Track who reads and replies
✅ **Time Savings**: No need to export/import CSV files
✅ **Real-time Data**: Always up-to-date customer information
✅ **Better ROI**: Target high-value and engaged customers

## Testing Checklist

- [ ] Add Shopify credentials to .env
- [ ] Restart Flask application
- [ ] Click "Sync Shopify" button
- [ ] Verify customers appear in list
- [ ] Test segment filtering
- [ ] Select customers and navigate to home
- [ ] Verify customers pre-selected on home page
- [ ] Send test message to selected customers
- [ ] Verify webhook updates customer engagement stats
- [ ] Check campaign details shows all messages (no 100 limit)
- [ ] Verify "View Reply" button appears when replied_at is set

## Known Limitations

1. Only customers with phone numbers are synced
2. Phone number must be in international format in Shopify
3. Webhook must be configured for engagement tracking
4. Large customer bases may take time for initial sync

## Next Steps

1. Add Shopify credentials to `.env` file
2. Restart your Flask application
3. Navigate to Customers page
4. Click "Sync Shopify" to import customers
5. Start sending targeted campaigns!

## Support

For issues or questions:
1. Check `SHOPIFY_INTEGRATION_GUIDE.md` for detailed documentation
2. Review application logs for error messages
3. Verify Shopify API credentials are correct
4. Ensure webhook is configured for engagement tracking
