import requests
import logging
from datetime import datetime

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
    
    def fetch_customers(self, limit=250):
        """Fetch all customers from Shopify"""
        all_customers = []
        url = f"{self.base_url}/customers.json?limit={limit}"
        
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
        # Get primary phone number
        phone = customer.get('phone') or customer.get('default_address', {}).get('phone', '')
        
        # Clean phone number (remove spaces, dashes, etc.)
        if phone:
            # Remove all non-digit characters except +
            cleaned_phone = ''.join(c for c in phone if c.isdigit() or c == '+')
            # Ensure it starts with + if it has digits
            if cleaned_phone:
                if not cleaned_phone.startswith('+'):
                    cleaned_phone = '+' + cleaned_phone
                phone = cleaned_phone
            else:
                phone = ''  # No valid phone number
        
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
