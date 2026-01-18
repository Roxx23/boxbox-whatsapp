# Customer Filtering & Custom Segments Guide

## Overview
The Customers page now supports advanced filtering by order value and number of orders, plus the ability to create custom segments for easy customer targeting.

## Features Added

### 1. **Advanced Filters**
Filter customers in real-time based on:

#### Order Value Range
- **Min Order Value**: Filter customers who spent at least this amount
- **Max Order Value**: Filter customers who spent up to this amount
- Example: Min $100, Max $500 shows customers who spent between $100-$500

#### Number of Orders
- **Min Orders**: Filter customers with at least this many orders
- **Max Orders**: Filter customers with up to this many orders
- Example: Min 3, Max 10 shows customers with 3-10 orders

### 2. **Custom Segments**
Create and save your own customer segments with specific criteria.

#### Creating a Custom Segment
1. Click "**Create Custom Segment**" button in the sidebar
2. Enter a **Segment Name** (e.g., "VIP Customers", "New Customers")
3. Set filter criteria:
   - Order Value Range (optional)
   - Number of Orders (optional)
4. Click "**Create Segment**"

The segment will appear in your segments list with the customer count.

#### Using Custom Segments
- Click on any custom segment to filter customers
- Segments persist across sessions
- Delete segments using the trash icon

#### Example Custom Segments
```
VIP Customers
- Min Order Value: $1000
- Min Orders: 5

New Customers
- Max Orders: 1

Dormant High Spenders
- Min Order Value: $500
- Max Order Value: $2000
```

### 3. **Predefined Segments**
Built-in segments that auto-calculate:
- **All Customers**: Everyone in your database
- **Has Phone Number**: Only customers with phone numbers
- **Engaged (Last 7 Days)**: Customers who read messages in last 7 days
- **Never Messaged**: Customers you haven't contacted yet
- **High Value (>$1000)**: Customers who spent over $1000
- **Has Orders**: Customers with at least one order
- **Replied to Messages**: Customers who replied to your messages

## How to Use

### Applying Quick Filters
1. Go to **Customers** page
2. Use the **Advanced Filters** card in the sidebar
3. Enter your criteria
4. Click "**Apply**"
5. Click "**Clear**" to reset filters

### Creating a Segment from Filters
1. Apply filters to find your target customers
2. Click "**Create Custom Segment**"
3. Enter the same criteria
4. Save for future use

### Sending Messages to Filtered Customers
1. Apply filters or select a segment
2. Check the boxes next to customers you want to message
3. Click "**Send Message to Selected**"
4. You'll be redirected to the home page with customers pre-selected

## Technical Details

### Database Changes
- Enhanced `get_all_customers()` to support order value and order count filters
- Added support for custom segment conditions stored as JSON
- New methods: `get_segment_by_id()`, `delete_segment()`

### API Endpoints
```
POST /api/segments/create
- Creates a new custom segment
- Body: {segment_name, min_order_value, max_order_value, min_orders, max_orders}

DELETE /api/segments/<id>/delete
- Deletes a custom segment
```

### Filter Parameters
Query string parameters supported:
- `segment`: Segment type or custom_<id>
- `min_order_value`: Minimum total spent
- `max_order_value`: Maximum total spent
- `min_orders`: Minimum number of orders
- `max_orders`: Maximum number of orders

### Example URLs
```
/customers?min_order_value=500&min_orders=2
/customers?segment=high_value
/customers?segment=custom_5
/customers?min_orders=1&max_orders=3
```

## Best Practices

### Segment Naming
- Use descriptive names: "VIP Customers" not "Segment 1"
- Include criteria in name: "Spent $500-1000"
- Keep names short for sidebar display

### Filter Combinations
- **New High Spenders**: Min Orders: 1, Min Order Value: $500
- **Repeat Customers**: Min Orders: 3
- **Budget Shoppers**: Max Order Value: $100
- **VIP Club**: Min Order Value: $1000, Min Orders: 5

### Message Targeting
1. Create segments for different customer tiers
2. Use filters to find specific customers for promotions
3. Combine with engagement metrics to re-engage dormant customers

## Examples

### Example 1: Target High-Value New Customers
```
Segment Name: "High-Value Newcomers"
- Min Order Value: $500
- Min Orders: 1
- Max Orders: 2
```

### Example 2: Re-engage Dormant VIPs
```
Segment Name: "Dormant VIPs"
- Min Order Value: $1000
- Use predefined: "Never Messaged"
```

### Example 3: Reward Loyal Customers
```
Segment Name: "Loyal Customers"
- Min Orders: 10
- Min Order Value: $100
```

## Troubleshooting

### Segment shows 0 customers
- Check if your criteria are too restrictive
- Verify customer data is synced from Shopify
- Ensure customers have order data

### Filter not working
- Clear filters and try again
- Check that values are numbers (no $ or commas)
- Reload the page

### Can't delete segment
- You can only delete custom segments
- Predefined segments can't be deleted
- Check if you're the segment owner

## Future Enhancements
Potential additions:
- Date-based filters (last purchase date)
- Tag-based filtering
- Location-based segments
- Engagement score filtering
- Export segments to CSV
