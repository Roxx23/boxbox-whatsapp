# Test Script - Verify Customer Filtering Implementation

## Steps to See Advanced Filters:

### 1. Restart the Flask Server
```bash
# Stop the current server (Ctrl+C)
# Then restart:
python app.py
```

### 2. Clear Browser Cache
- Press `Ctrl + Shift + R` (Windows/Linux) or `Cmd + Shift + R` (Mac)
- Or open browser DevTools (F12) and right-click refresh button → "Empty Cache and Hard Reload"

### 3. Navigate to Customers Page
```
http://localhost:5000/customers
```

### 4. What You Should See

**Left Sidebar (col-md-3):**
1. **Segments Card** (top)
   - All default segments listed
   - "Create Custom Segment" button at bottom
   
2. **Advanced Filters Card** (below segments)
   - Header: "Advanced Filters" with slider icon
   - Order Value Range fields (Min $ / Max $)
   - Number of Orders fields (Min / Max)
   - "Apply" button (blue)
   - "Clear" button (gray)

**Right Side (col-md-9):**
- Customer table with all customers

### 5. Test the Filters

#### Test 1: Filter by Order Value
1. Enter `100` in "Min $" field
2. Enter `500` in "Max $" field
3. Click "Apply"
4. Should show only customers who spent between $100-$500

#### Test 2: Filter by Order Count
1. Click "Clear" to reset
2. Enter `2` in Min Orders
3. Enter `5` in Max Orders
4. Click "Apply"
5. Should show only customers with 2-5 orders

#### Test 3: Combined Filters
1. Min Order Value: `200`
2. Min Orders: `3`
3. Click "Apply"
4. Should show customers with $200+ spent AND 3+ orders

### 6. Troubleshooting

#### If you don't see Advanced Filters card:

**Check 1: Verify Template File**
```bash
# Open customers.html and search for "Advanced Filters"
# Line should be around 143
grep -n "Advanced Filters" templates/customers.html
```

**Check 2: Check Server Logs**
```
# Look for any errors when loading /customers route
# Should see: GET /customers 200
```

**Check 3: Inspect Browser Console**
- Open DevTools (F12)
- Check Console tab for JavaScript errors
- Check Network tab - verify customers.html loaded correctly

**Check 4: Verify Bootstrap Grid**
- The page uses Bootstrap col-md-3 for sidebar
- On small screens (<768px), sidebar moves to top
- Make sure your window is wide enough

**Check 5: Check if filters variable is passed**
Add this debug line to app.py temporarily:
```python
# In customers_page() function, before return:
logger.info(f"Filters being passed: {filters}")
```

#### If Advanced Filters card appears but doesn't work:

**Check 1: Form submission**
- Open DevTools Network tab
- Enter filter values and click Apply
- Should see GET request to `/customers?min_order_value=...`

**Check 2: Database has customer data**
- Make sure you've synced Shopify customers
- Check customers have order_count and total_spent values

**Check 3: Check backend logs**
```python
# The get_all_customers() function should process filters
# Add debug logging to see what filters are applied
```

### 7. Expected HTML Structure

```html
<div class="container-fluid mt-4">
    <div class="row">
        <div class="col-md-3">
            <!-- Segments Card -->
            <div class="content-card">
                <!-- Segments list -->
            </div>
            
            <!-- Advanced Filters Card -->
            <div class="content-card mt-3">
                <h5>Advanced Filters</h5>
                <form>
                    <!-- Filter inputs -->
                </form>
            </div>
        </div>
        
        <div class="col-md-9">
            <!-- Customer table -->
        </div>
    </div>
</div>
```

### 8. Quick Visual Check

Use browser DevTools Elements inspector:
1. Press F12
2. Click the inspector tool (top-left icon)
3. Hover over the left sidebar
4. Should see two `.content-card` elements
5. Second one should contain "Advanced Filters"

If you still can't see it, let me know and I'll check the HTML structure more carefully!
