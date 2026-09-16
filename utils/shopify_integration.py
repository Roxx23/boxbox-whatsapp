import requests
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class ShopifyIntegration:
    """Shopify integration for fetching customer data"""
    
    def __init__(self, shop_name, access_token):
        self.shop_name = shop_name
        self.access_token = access_token
        self.base_url = f"https://{shop_name}.myshopify.com/admin/api/2024-01"
        self.headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json"
        }
    
    def fetch_customers(self, limit=250, created_at_min=None):
        """Fetch customers from Shopify, optionally only those created after created_at_min."""
        all_customers = []
        params = f"limit={limit}"
        if created_at_min:
            params += f"&created_at_min={created_at_min}"
        url = f"{self.base_url}/customers.json?{params}"
        
        while url:
            try:
                logger.info(f"🔄 Fetching from: {url}")
                response = requests.get(url, headers=self.headers, timeout=30)
                
                logger.info(f"📊 Response status: {response.status_code}")
                
                if response.status_code == 401:
                    logger.error("❌ Authentication failed. Check your SHOPIFY_ACCESS_TOKEN")
                    break
                elif response.status_code == 404:
                    logger.error("❌ Store not found. Check your SHOPIFY_SHOP_NAME")
                    break
                elif response.status_code == 204:
                    logger.info("ℹ️ No content returned (empty response)")
                    break
                    
                response.raise_for_status()
                
                # Check if response has content
                if not response.text or response.text.strip() == '':
                    logger.error("❌ Empty response from Shopify")
                    break
                
                # Try to parse JSON
                try:
                    data = response.json()
                except ValueError as json_err:
                    logger.error(f"❌ JSON parsing error: {json_err}")
                    logger.error(f"Response text: {response.text[:500]}")
                    break
                
                customers = data.get('customers', [])
                all_customers.extend(customers)
                
                logger.info(f"✅ Fetched {len(customers)} customers (Total: {len(all_customers)})")
                
                # Check for pagination
                link_header = response.headers.get('Link', '')
                if 'rel="next"' in link_header:
                    # Extract next page URL
                    next_link = [l.strip() for l in link_header.split(',') if 'rel="next"' in l]
                    if next_link:
                        url = next_link[0].split(';')[0].strip('<>')
                    else:
                        url = None
                else:
                    url = None
                
            except requests.exceptions.RequestException as e:
                logger.error(f"❌ HTTP Error fetching customers: {e}")
                if hasattr(e, 'response') and hasattr(e.response, 'text'):
                    logger.error(f"Response: {e.response.text[:500]}")
                break
            except Exception as e:
                logger.error(f"❌ Error fetching customers from Shopify: {e}")
                import traceback
                logger.error(traceback.format_exc())
                break
        
        logger.info(f"📊 Total customers fetched: {len(all_customers)}")
        return all_customers
    
    def get_customer_orders(self, customer_id):
        """Get orders for a specific customer"""
        try:
            url = f"{self.base_url}/customers/{customer_id}/orders.json"
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            # Check for empty response
            if not response.text or response.text.strip() == '':
                logger.warning(f"Empty response for customer {customer_id} orders")
                return []
            
            return response.json().get('orders', [])
        except ValueError as json_err:
            logger.error(f"JSON parsing error for customer {customer_id} orders: {json_err}")
            return []
        except Exception as e:
            logger.error(f"Error fetching orders for customer {customer_id}: {e}")
            return []
    
    def parse_customer_data(self, customer):
        """Parse Shopify customer data to our format"""
        # Collect phone candidates: top-level, default_address, any address
        default_address = customer.get('default_address') or {}
        addresses = customer.get('addresses') or []
        phone_candidates = [
            customer.get('phone') or '',
            default_address.get('phone') or '',
        ] + [a.get('phone') or '' for a in addresses]

        phone = ''
        for candidate in phone_candidates:
            if not candidate:
                continue
            cleaned = ''.join(c for c in candidate if c.isdigit() or c == '+')
            if not cleaned:
                continue
            # Normalise to E.164 (+91XXXXXXXXXX for Indian numbers)
            if cleaned.startswith('+'):
                # Already has country code
                phone = cleaned
            elif cleaned.startswith('91') and len(cleaned) == 12:
                # 91XXXXXXXXXX → +91XXXXXXXXXX
                phone = '+' + cleaned
            elif cleaned.startswith('0') and len(cleaned) == 11:
                # 0XXXXXXXXXX → +91XXXXXXXXXX
                phone = '+91' + cleaned[1:]
            elif len(cleaned) == 10:
                # XXXXXXXXXX → +91XXXXXXXXXX
                phone = '+91' + cleaned
            else:
                # Unknown format — prepend + and hope for the best
                phone = '+' + cleaned
            break
        
        return {
            'shopify_id': customer.get('id'),
            'first_name': customer.get('first_name', ''),
            'last_name': customer.get('last_name', ''),
            'email': customer.get('email', ''),
            'phone': phone,
            'total_spent': float(customer.get('total_spent', 0)),
            'orders_count': customer.get('orders_count', 0),
            'state': customer.get('state', 'enabled'),
            'tags': customer.get('tags', ''),
            'created_at': customer.get('created_at', ''),
            'updated_at': customer.get('updated_at', '')
        }

    def create_price_rule_with_discount_code(self, discount_code, percentage=5, ends_at=None):
        """Create a Shopify price rule with a one-time-use discount code.

        Args:
            discount_code: The code string (e.g., 'BOXBOX5-abc123')
            percentage: Discount percentage (default 5)
            ends_at: ISO 8601 expiry timestamp, or None for no expiry (default None)

        Returns:
            (price_rule_id, generated_code) on success, (None, None) on failure
        """
        try:
            # Step 1: Create Price Rule
            price_rule_payload = {
                "price_rule": {
                    "title": f"Abandoned Cart Reminder - {discount_code}",
                    "target_type": "line_item",
                    "target_selection": "all",
                    "allocation_method": "across",
                    "value_type": "percentage",
                    "value": f"-{percentage}",
                    "usage_limit": 1,
                    "starts_at": datetime.now(timezone.utc).isoformat(),
                    "ends_at": ends_at
                }
            }

            url = f"{self.base_url}/price_rules.json"
            response = requests.post(url, headers=self.headers, json=price_rule_payload, timeout=30)

            if response.status_code != 201:
                logger.error(f"❌ Failed to create price rule: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return None, None

            price_rule_data = response.json()
            price_rule_id = price_rule_data['price_rule']['id']
            logger.info(f"✅ Created price rule {price_rule_id}")

            # Step 2: Create Discount Code
            discount_code_payload = {
                "discount_code": {
                    "price_rule_id": price_rule_id,
                    "code": discount_code
                }
            }

            url = f"{self.base_url}/price_rules/{price_rule_id}/discount_codes.json"
            response = requests.post(url, headers=self.headers, json=discount_code_payload, timeout=30)

            if response.status_code != 201:
                logger.error(f"❌ Failed to create discount code: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return price_rule_id, None

            code_data = response.json()
            generated_code = code_data['discount_code']['code']
            logger.info(f"✅ Created discount code: {generated_code}")

            return price_rule_id, generated_code

        except Exception as e:
            logger.error(f"❌ Error creating price rule/discount code: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None, None
