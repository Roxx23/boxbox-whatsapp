# ✏️ Manual Button Parameter Input

## ✅ What Changed

**Before**: Button parameters were mapped from CSV columns (different code per recipient)

**Now**: Button parameters are typed manually (same code for all recipients)

---

## 🎯 How It Works Now

### For COPY_CODE Buttons

**UI Shows:**
```
📋 Copy Code Button - Coupon Code
[Enter coupon code (same for all recipients)_____]
ℹ️ This code will be sent to ALL recipients
```

**You Type:**
```
NEWYEAR2025
```

**Result**: ALL recipients get the same coupon code `NEWYEAR2025`

---

## 📋 Example Usage

### Your Template: `new_year_2025_campaign`

**Step 1**: Upload CSV
```csv
Name,Phone
Ayush,+919702760931
John,+919876543210
Jane,+918765432109
```

**Step 2**: Select Template
- Choose `new_year_2025_campaign`

**Step 3**: Fill Fields
1. **Parameter 1** → Select `Name`
2. **📋 Copy Code - Coupon Code** → Type `ITS2026BRO`
3. **Upload image** in Header Image field

**Step 4**: Send
- All 3 recipients get messages with `ITS2026BRO` coupon code

---

## 🔄 Different Use Cases

### Use Case 1: Same Code for Everyone ✅ (Current)
**Scenario**: New Year promotion - everyone gets same code

**Input Type**: Text field (manual entry)

**Example**:
```
Coupon Code: NEWYEAR2025
```

**Result**:
- Ayush gets: NEWYEAR2025
- John gets: NEWYEAR2025
- Jane gets: NEWYEAR2025

### Use Case 2: Unique Code Per Person (If Needed Later)
**Scenario**: Personalized referral codes

**Input Type**: CSV column mapping

**CSV**:
```csv
Name,Phone,UniqueCode
Ayush,+919702760931,AYUSH123
John,+919876543210,JOHN456
```

**Result**:
- Ayush gets: AYUSH123
- John gets: JOHN456

*Note: This requires adding a toggle option in the future*

---

## 🖥️ Dashboard Changes

### Requirements Banner
**Shows:**
```
ℹ️ Template Requirements:
• IMAGE Header: Upload an image above
• Copy Code Button: Enter a coupon code below (same for all recipients)
```

### Button Field
**Before** (dropdown):
```
📋 Coupon Code Column
[Select CSV Column ▼]
```

**After** (text input):
```
📋 Coupon Code
[Enter coupon code (same for all recipients)_____]
```

---

## 💡 Benefits

✅ **Simpler**: Just type the code
✅ **Faster**: No need to add column to CSV
✅ **Clearer**: Shows "same for all recipients"
✅ **Common Use Case**: Most campaigns use same promo code

---

## 📝 CSV Format

**You DON'T need** a coupon column anymore:

**Simple CSV:**
```csv
Name,Phone
Ayush,+919702760931
John,+919876543210
```

**Just type the coupon code** in the dashboard form field!

---

## 🎯 Complete Example

### Template: `new_year_2025_campaign`

**Has:**
- IMAGE header
- Body with {{1}} (Name)
- COPY_CODE button
- URL button

**Dashboard Form:**

1. **📤 Upload CSV:**
   ```csv
   Name,Phone
   Ayush,+919702760931
   ```

2. **📝 Select Template:**
   - `new_year_2025_campaign`

3. **🔗 Map Parameters:**
   - Parameter 1 → `Name`

4. **📋 Button Parameters:**
   - Coupon Code: `ITS2026BRO` ← **Type this!**

5. **🖼️ Upload Image:**
   - Upload new_year_2025.jpg

6. **🚀 Send:**
   - Click "Send Now"

**Result:**
```
Message to Ayush:
[New Year Image]
Hi Ayush, welcome 2025!
[📋 Copy Code] ITS2026BRO
[🔗 Visit Website]
```

---

## ⚠️ Important Notes

### Same Code for All Recipients
- The coupon code you enter will be sent to **everyone** in the CSV
- If you need unique codes, add them to CSV and we can add that feature

### Required Field
- The coupon code field is **required**
- You must enter something (can't be empty)

### Dynamic URLs Still Use CSV
- URL buttons with {{1}} still need CSV column mapping
- This is for unique values (order IDs, tracking numbers)

---

## 🧪 Test It

1. **Refresh dashboard** (Ctrl+F5)
2. **Upload simple CSV:**
   ```csv
   Name,Phone
   Test,+919702760931
   ```

3. **Select template** with copy code button

4. **See text input** instead of dropdown

5. **Type coupon code**: `TEST2025`

6. **Send** and verify!

---

## ✅ Status

- ✅ UI updated to text input
- ✅ Backend updated to handle manual input
- ✅ Requirements banner updated
- ✅ Help text clarified
- ✅ Ready to use!

**Refresh your browser and try it now!** 🎉
