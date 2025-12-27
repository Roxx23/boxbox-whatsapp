"""
Simple example: Send WhatsApp template with copy_code button

This demonstrates the fix for error:
(#131008) Required parameter is missing - coupon_code
"""

from utils.whatsapp import send_template

# =============================================================================
# EXAMPLE 1: Single Message with Copy Code Button
# =============================================================================

def example_single_message():
    """Send one message with coupon code"""
    
    print("📤 Example 1: Single message with copy code button")
    
    # Your configuration
    phone = "+919156143465"  # Recipient's WhatsApp number
    template_name = "your_template_name"  # Replace with your template name
    coupon_code = "SAVE20"  # The coupon code to send
    
    # Send message
    status, response = send_template(
        number=phone,
        template_name=template_name,
        params=[],  # Body parameters (e.g., ["John", "Doe"] if template has {{1}}, {{2}})
        lang="en_US",
        button_params={"copy_code": coupon_code}  # 👈 THE FIX!
    )
    
    # Check result
    if status == 200:
        print(f"✅ Success! Message sent to {phone}")
        print(f"📨 Response: {response}")
    else:
        print(f"❌ Failed with status {status}")
        print(f"❌ Error: {response}")


# =============================================================================
# EXAMPLE 2: Bulk Messages from CSV
# =============================================================================

def example_bulk_from_csv():
    """Send to multiple recipients from CSV"""
    
    print("\n📤 Example 2: Bulk messages from CSV")
    
    import pandas as pd
    
    # Load CSV
    # Expected format:
    # Name,Phone,CouponCode
    # John,+919156143465,SAVE20
    # Jane,+919876543210,WELCOME10
    
    csv_file = "contacts.csv"  # Your CSV file
    template_name = "your_template_name"  # Your template
    
    try:
        df = pd.read_csv(csv_file)
        
        # Validate columns
        required_cols = ["Phone", "CouponCode"]
        for col in required_cols:
            if col not in df.columns:
                print(f"❌ Missing column: {col}")
                return
        
        # Send to each recipient
        success_count = 0
        failed_count = 0
        
        for idx, row in df.iterrows():
            phone = str(row["Phone"])
            coupon = str(row["CouponCode"])
            name = row.get("Name", "Customer")  # Optional name column
            
            print(f"\n📞 Sending to {name} ({phone})...")
            
            # Send with coupon code button
            status, response = send_template(
                number=phone,
                template_name=template_name,
                params=[name],  # If template uses {{1}} for name
                lang="en_US",
                button_params={"copy_code": coupon}  # 👈 THE FIX!
            )
            
            if status == 200:
                print(f"   ✅ Sent successfully")
                success_count += 1
            else:
                print(f"   ❌ Failed: {response}")
                failed_count += 1
            
            # Rate limiting (optional)
            import time
            time.sleep(1)  # Wait 1 second between messages
        
        # Summary
        print("\n" + "="*50)
        print(f"📊 SUMMARY:")
        print(f"   ✅ Successful: {success_count}")
        print(f"   ❌ Failed: {failed_count}")
        print(f"   📈 Total: {len(df)}")
        print("="*50)
    
    except FileNotFoundError:
        print(f"❌ File not found: {csv_file}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


# =============================================================================
# EXAMPLE 3: With Body Parameters AND Button Parameters
# =============================================================================

def example_with_body_params():
    """Template with both body parameters and button parameters"""
    
    print("\n📤 Example 3: Body parameters + Button parameters")
    
    # Scenario: Template with body variables AND copy code button
    # Template body: "Hi {{1}}, get {{2}}% off with code below!"
    # Template button: COPY_CODE
    
    phone = "+919156143465"
    template_name = "your_template_name"
    customer_name = "John"
    discount_percent = "20"
    coupon_code = "SAVE20"
    
    status, response = send_template(
        number=phone,
        template_name=template_name,
        params=[customer_name, discount_percent],  # For {{1}} and {{2}}
        lang="en_US",
        button_params={"copy_code": coupon_code}  # For copy button
    )
    
    if status == 200:
        print(f"✅ Success! Message sent with body params and button")
    else:
        print(f"❌ Failed: {response}")


# =============================================================================
# EXAMPLE 4: Dynamic URL Button (Alternative button type)
# =============================================================================

def example_dynamic_url():
    """Template with dynamic URL button"""
    
    print("\n📤 Example 4: Dynamic URL button")
    
    # Scenario: Template with URL button containing variable
    # Button URL: https://example.com/order/{{1}}
    
    phone = "+919156143465"
    template_name = "your_template_name"
    order_id = "12345"
    
    status, response = send_template(
        number=phone,
        template_name=template_name,
        params=[],
        lang="en_US",
        button_params={"url_index_0": order_id}  # For first URL button
    )
    
    if status == 200:
        print(f"✅ Success! Message sent with dynamic URL")
    else:
        print(f"❌ Failed: {response}")


# =============================================================================
# EXAMPLE 5: Multiple Button Parameters
# =============================================================================

def example_multiple_buttons():
    """Template with multiple button parameters"""
    
    print("\n📤 Example 5: Multiple button parameters")
    
    # Scenario: Template with COPY_CODE button AND dynamic URL button
    
    phone = "+919156143465"
    template_name = "your_template_name"
    coupon_code = "SAVE20"
    order_id = "12345"
    
    status, response = send_template(
        number=phone,
        template_name=template_name,
        params=[],
        lang="en_US",
        button_params={
            "copy_code": coupon_code,      # First button (copy code)
            "url_index_0": order_id         # Second button (URL with parameter)
        }
    )
    
    if status == 200:
        print(f"✅ Success! Message sent with multiple buttons")
    else:
        print(f"❌ Failed: {response}")


# =============================================================================
# RUN EXAMPLES
# =============================================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🔧 WhatsApp Template Button Examples")
    print("="*60)
    
    print("\nChoose an example to run:")
    print("1. Single message with copy code button")
    print("2. Bulk messages from CSV")
    print("3. Body parameters + Button parameters")
    print("4. Dynamic URL button")
    print("5. Multiple button parameters")
    print("0. Exit")
    
    try:
        choice = input("\nEnter choice (0-5): ").strip()
        
        if choice == "1":
            example_single_message()
        elif choice == "2":
            example_bulk_from_csv()
        elif choice == "3":
            example_with_body_params()
        elif choice == "4":
            example_dynamic_url()
        elif choice == "5":
            example_multiple_buttons()
        elif choice == "0":
            print("👋 Goodbye!")
        else:
            print("❌ Invalid choice")
    
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted. Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*60)
