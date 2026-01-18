# Shopify Integration Guide

## Overview
This integration allows you to automatically sync customers from your Shopify store and segment them for targeted WhatsApp campaigns.

## Setup Instructions

### 1. Get Shopify API Credentials

1. Log in to your Shopify admin panel
2. Go to **Settings** → **Apps and sales channels** → **Develop apps**
3. Click **Create an app**
4. Give it a name (e.g., "WhatsApp Integration")
5. Click **Configure Admin API scopes**
6. Select these permissions:
   - `read_customers`
   - `read_orders`
7. Click **Save**
8. Go to **API credentials** tab
9. Click **Install app**
10. Copy the **Admin API access token**

### 2. Add Credentials to .env File

Add these lines to your `.env` file:

```
SHOPIFY_SHOP_NAME=your-store-name
SHOPIFY_ACCESS_TOKEN=shpat_xxxxxxxxxxxxx
```

**Important:** 
- `SHOPIFY_SHOP_NAME` should be just the store name, not the full URL
- Example: If your store is `mystore.myshopify.com`, use `mystore`

### 3. Sync Customers

1. Go to the **Customers** page in the dashboard
2. Click **Sync Shopify** button
3. Wait for the sync to complete
4. Your customers will be imported with:
   - Name
   - Phone number
   - Email
   - Total spent
   - Order count
   - Tags

## Features

### Automatic Segmentation

The system automatically creates these segments:

1. **All Customers** - All imported customers
2. **Has Phone Number** - Customers with valid phone numbers
3. **Engaged (Last 7 Days)** - Customers who read messages in the last 7 days
4. **Never Messaged** - Customers who haven't been contacted yet
5. **High Value (>$1000)** - Customers who spent more than $1000
6. **Has Orders** - Customers with at least one order
7. **Replied to Messages** - Customers who replied to your messages

### Customer Engagement Tracking

The system automatically tracks:
- **Messages Sent** - Total messages sent to each customer
- **Messages Read** - How many messages they read
- **Messages Replied** - How many times they replied
- **Last Message Sent** - Date of last message
- **Last Message Read** - Date of last read
- **Last Message Replied** - Date of last reply

### Sending Messages to Customers

1. Go to the **Customers** page
2. Select a segment (or view all customers)
3. Check the customers you want to message
4. Click **Send Message to Selected**
5. You'll be redirected to the home page with customers pre-selected
6. Choose your template and send!

## API Endpoints

### Sync Shopify Customers
```
POST /api/sync-shopify
```
Syncs all customers from Shopify store.

### Get Customers by Segment
```
GET /api/customers/<segment>
```
Returns customers filtered by segment type.

Segment types:
- `all` - All customers
- `has_phone` - Has phone number
- `engaged_last_7_days` - Engaged in last 7 days
- `no_message_sent` - Never messaged
- `high_value` - Spent > $1000
- `has_orders` - Has orders
- `replied` - Has replied to messages

## Database Tables

### customers
Stores Shopify customer data:
- `shopify_id` - Shopify customer ID
- `first_name`, `last_name` - Customer name
- `email`, `phone` - Contact info
- `total_spent` - Total amount spent
- `orders_count` - Number of orders
- `tags` - Shopify tags
- `messages_sent_count` - Total messages sent
- `messages_read_count` - Total messages read
- `messages_replied_count` - Total replies
- `last_message_sent` - Last message timestamp
- `last_message_read` - Last read timestamp
- `last_message_replied` - Last reply timestamp

### customer_segments
Custom customer segments:
- `segment_name` - Name of segment
- `segment_type` - Type identifier
- `conditions` - JSON conditions
- `customer_count` - Number of customers

## Troubleshooting

### "Shopify credentials not configured"
- Make sure you added `SHOPIFY_SHOP_NAME` and `SHOPIFY_ACCESS_TOKEN` to your `.env` file
- Restart your Flask application after adding credentials

### "No customers synced"
- Check if your customers have phone numbers in Shopify
- Only customers with phone numbers are synced
- Verify API permissions include `read_customers`

### "Error syncing customers"
- Check your Shopify API access token is valid
- Verify your shop name is correct (without `.myshopify.com`)
- Check application logs for detailed error messages

## Best Practices

1. **Initial Sync**: Run the first sync during off-peak hours as it may take time for large customer bases
2. **Regular Updates**: Sync customers regularly (daily/weekly) to keep data fresh
3. **Segmentation**: Use segments to target specific customer groups for better engagement
4. **Testing**: Test with a small segment before sending to all customers
5. **Compliance**: Ensure you have consent to send WhatsApp messages to customers

## Privacy & Compliance

- Customer phone numbers are stored securely in your local database
- No data is shared with third parties
- Ensure compliance with:
  - WhatsApp Business Policy
  - GDPR (if applicable)
  - Local data protection laws
  - Your Shopify store's privacy policy

## Future Enhancements

Planned features:
- [ ] Automatic sync scheduling
- [ ] Advanced custom segments with AND/OR conditions
- [ ] Integration with Shopify webhooks for real-time updates
- [ ] Customer journey tracking
- [ ] Abandoned cart recovery campaigns
- [ ] Order status notifications
