# Database models for campaign tracking and analytics
import sqlite3
import json
import logging
import os
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class Database:
    """Database manager for campaign tracking"""
    
    def __init__(self, db_path=None):
        # Support persistent storage on Render.com
        if db_path is None:
            db_path = os.getenv('DATABASE_PATH', 'whatsapp_dashboard.db')
        
        # Ensure directory exists for persistent storage
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"Created database directory: {db_dir}")
        
        self.db_path = db_path
        logger.info(f"Using database at: {self.db_path}")
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def init_database(self):
        """Initialize database tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Campaigns table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS campaigns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    campaign_name TEXT,
                    campaign_type TEXT NOT NULL,
                    template_name TEXT,
                    recipient_count INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    failed_count INTEGER DEFAULT 0,
                    delivered_count INTEGER DEFAULT 0,
                    read_count INTEGER DEFAULT 0,
                    replied_count INTEGER DEFAULT 0,
                    clicked_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    scheduled_time TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            # Messages table (individual message tracking)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    phone_number TEXT NOT NULL,
                    recipient_name TEXT,
                    message_content TEXT,
                    template_name TEXT,
                    status TEXT DEFAULT 'pending',
                    error_message TEXT,
                    sent_at TEXT,
                    delivered_at TEXT,
                    read_at TEXT,
                    replied_at TEXT,
                    reply_text TEXT,
                    clicked_at TEXT,
                    whatsapp_message_id TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id),
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            # User activity log
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS activity_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT,
                    ip_address TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            # Templates usage tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS template_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    template_name TEXT NOT NULL,
                    times_used INTEGER DEFAULT 1,
                    last_used TEXT DEFAULT CURRENT_TIMESTAMP,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            # User sessions
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    login_time TEXT DEFAULT CURRENT_TIMESTAMP,
                    logout_time TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            # Customers table (Shopify integration)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS customers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    shopify_id TEXT UNIQUE,
                    first_name TEXT,
                    last_name TEXT,
                    email TEXT,
                    phone TEXT,
                    total_spent REAL DEFAULT 0,
                    orders_count INTEGER DEFAULT 0,
                    state TEXT DEFAULT 'enabled',
                    tags TEXT,
                    last_message_sent TEXT,
                    last_message_read TEXT,
                    last_message_replied TEXT,
                    messages_sent_count INTEGER DEFAULT 0,
                    messages_read_count INTEGER DEFAULT 0,
                    messages_replied_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            # Customer segments table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS customer_segments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    segment_name TEXT NOT NULL,
                    segment_type TEXT NOT NULL,
                    conditions TEXT,
                    customer_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            # Abandoned carts table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS abandoned_carts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    shopify_cart_id TEXT UNIQUE,
                    customer_id TEXT,
                    customer_email TEXT,
                    customer_phone TEXT,
                    cart_token TEXT,
                    cart_items TEXT,
                    total_price REAL,
                    currency TEXT,
                    abandoned_at TEXT,
                    reminder_sent BOOLEAN DEFAULT 0,
                    reminder_sent_at TEXT,
                    recovered BOOLEAN DEFAULT 0,
                    recovered_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            # Orders table (for order confirmations)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS shopify_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    shopify_order_id TEXT UNIQUE,
                    order_number TEXT,
                    customer_id TEXT,
                    customer_email TEXT,
                    customer_phone TEXT,
                    total_price REAL,
                    currency TEXT,
                    financial_status TEXT,
                    fulfillment_status TEXT,
                    order_items TEXT,
                    confirmation_sent BOOLEAN DEFAULT 0,
                    confirmation_sent_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            # Automation settings table (order confirmation, fulfillment, abandoned cart)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS automation_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    enabled INTEGER DEFAULT 0,
                    template_name TEXT DEFAULT '',
                    template_language TEXT DEFAULT 'en_US',
                    delay_hours INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, event_type)
                )
            ''')

            # Add shopify_created_at column if it doesn't exist (migration for existing DBs)
            try:
                cursor.execute('ALTER TABLE customers ADD COLUMN shopify_created_at TEXT')
            except Exception:
                pass

            # Add template send params columns to messages (migration for existing DBs)
            for col in [
                'ALTER TABLE messages ADD COLUMN template_params TEXT',
                'ALTER TABLE messages ADD COLUMN template_language TEXT',
                'ALTER TABLE messages ADD COLUMN button_params TEXT',
                'ALTER TABLE messages ADD COLUMN header_media_id TEXT',
            ]:
                try:
                    cursor.execute(col)
                except Exception:
                    pass

            # Migrations for automation features
            for col in [
                'ALTER TABLE shopify_orders ADD COLUMN fulfillment_sent INTEGER DEFAULT 0',
                'ALTER TABLE shopify_orders ADD COLUMN fulfillment_sent_at TEXT',
                'ALTER TABLE abandoned_carts ADD COLUMN cart_url TEXT',
                "ALTER TABLE automation_settings ADD COLUMN extra_data TEXT DEFAULT '{}'",
                'ALTER TABLE shopify_orders ADD COLUMN tracking_url TEXT',
                'ALTER TABLE abandoned_carts ADD COLUMN customer_name TEXT',
                'ALTER TABLE shopify_orders ADD COLUMN tracking_number TEXT',
                'ALTER TABLE shopify_orders ADD COLUMN tracking_company TEXT',
                'ALTER TABLE shopify_orders ADD COLUMN order_status_url TEXT',
            ]:
                try:
                    cursor.execute(col)
                except Exception:
                    pass

            conn.commit()

    # Campaign Methods
    def create_campaign(self, user_id, username, campaign_name, campaign_type, 
                       template_name=None, recipient_count=0, scheduled_time=None):
        """Create a new campaign"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO campaigns (user_id, username, campaign_name, campaign_type, 
                                     template_name, recipient_count, scheduled_time, started_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, username, campaign_name, campaign_type, template_name, 
                  recipient_count, scheduled_time, datetime.now().isoformat()))
            
            return cursor.lastrowid
    
    def update_campaign_status(self, campaign_id, status, success_count=None, 
                              failed_count=None, completed_at=None):
        """Update campaign status"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            updates = ['status = ?']
            params = [status]
            
            if success_count is not None:
                updates.append('success_count = ?')
                params.append(success_count)
            
            if failed_count is not None:
                updates.append('failed_count = ?')
                params.append(failed_count)
            
            if completed_at:
                updates.append('completed_at = ?')
                params.append(completed_at)
            
            params.append(campaign_id)
            
            cursor.execute(f'''
                UPDATE campaigns 
                SET {', '.join(updates)}
                WHERE id = ?
            ''', params)
    
    def get_campaign(self, campaign_id):
        """Get campaign by ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM campaigns WHERE id = ?', (campaign_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_user_campaigns(self, user_id, limit=None):
        """Get campaigns for a user. Pass limit=N to cap results; omit for all."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if limit is not None:
                cursor.execute('''
                    SELECT * FROM campaigns
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (user_id, limit))
            else:
                cursor.execute('''
                    SELECT * FROM campaigns
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                ''', (user_id,))

            return [dict(row) for row in cursor.fetchall()]
    
    def delete_campaign(self, campaign_id):
        """Delete a campaign and all its messages"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM messages WHERE campaign_id = ?', (campaign_id,))
            cursor.execute('DELETE FROM campaigns WHERE id = ?', (campaign_id,))

    def add_to_campaign_recipient_count(self, campaign_id, count):
        """Increment an existing campaign's recipient_count by count"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE campaigns
                SET recipient_count = recipient_count + ?
                WHERE id = ?
            ''', (count, campaign_id))

    def get_all_campaigns(self, limit=100):
        """Get all campaigns (admin view)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM campaigns 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    # Message Methods
    def add_message(self, campaign_id, user_id, phone_number, recipient_name=None,
                   message_content=None, template_name=None, status='pending',
                   template_params=None, template_language=None, button_params=None,
                   header_media_id=None):
        """Add a message to campaign"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO messages (campaign_id, user_id, phone_number, recipient_name,
                                    message_content, template_name, status,
                                    template_params, template_language, button_params,
                                    header_media_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (campaign_id, user_id, phone_number, recipient_name,
                  message_content, template_name, status,
                  json.dumps(template_params) if template_params is not None else None,
                  template_language,
                  json.dumps(button_params) if button_params is not None else None,
                  header_media_id))
            return cursor.lastrowid

    def fail_message_by_whatsapp_id(self, whatsapp_message_id, error_code, error_message):
        """Mark a message as failed (e.g. 131049) and adjust campaign counts."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id, campaign_id, status FROM messages WHERE whatsapp_message_id = ?',
                (whatsapp_message_id,)
            )
            row = cursor.fetchone()
            if not row:
                return
            msg = dict(row)
            if msg['status'] == 'failed':
                return  # already failed — avoid double-counting campaign stats
            cursor.execute(
                "UPDATE messages SET status = 'failed', error_message = ? WHERE whatsapp_message_id = ?",
                (f"[{error_code}] {error_message}", whatsapp_message_id)
            )
            # Any previously-counted status (sent/delivered/read/replied) must move
            # from success_count → failed_count. Only 'sent' was handled before; this
            # also covers late "failed" webhooks that arrive after a "delivered" event.
            if msg['status'] in ('sent', 'delivered', 'read', 'replied') and msg['campaign_id']:
                cursor.execute('''
                    UPDATE campaigns
                    SET success_count = MAX(0, success_count - 1),
                        failed_count  = failed_count + 1
                    WHERE id = ?
                ''', (msg['campaign_id'],))

    def get_unsent_campaign_messages(self, campaign_id):
        """Return failed/queued messages for a campaign."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, phone_number, recipient_name, template_name,
                       message_content, template_params, template_language, button_params,
                       header_media_id
                FROM messages
                WHERE campaign_id = ? AND status IN ('failed', 'queued')
            ''', (campaign_id,))
            return [dict(row) for row in cursor.fetchall()]

    def reset_messages_for_resend(self, campaign_id):
        """Reset failed/queued messages back to queued and fix campaign counts."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM messages WHERE campaign_id = ? AND status IN ('failed','queued')",
                (campaign_id,)
            )
            count = cursor.fetchone()[0]
            if not count:
                return 0
            cursor.execute('''
                UPDATE messages
                SET status = 'queued', error_message = NULL,
                    sent_at = NULL, whatsapp_message_id = NULL
                WHERE campaign_id = ? AND status IN ('failed', 'queued')
            ''', (campaign_id,))
            cursor.execute('''
                UPDATE campaigns
                SET failed_count = MAX(0, failed_count - ?),
                    status = 'running', completed_at = NULL
                WHERE id = ?
            ''', (count, campaign_id))
            return count
    
    def update_message_status(self, message_id, status, error_message=None, sent_at=None, whatsapp_message_id=None):
        """Update message status"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if sent_at is None and status == 'sent':
                sent_at = datetime.now().isoformat()
            
            if whatsapp_message_id:
                cursor.execute('''
                    UPDATE messages 
                    SET status = ?, error_message = ?, sent_at = ?, whatsapp_message_id = ?
                    WHERE id = ?
                ''', (status, error_message, sent_at, whatsapp_message_id, message_id))
            else:
                cursor.execute('''
                    UPDATE messages 
                    SET status = ?, error_message = ?, sent_at = ?
                    WHERE id = ?
                ''', (status, error_message, sent_at, message_id))
    
    def update_message_engagement(self, whatsapp_message_id, engagement_type, timestamp=None, reply_text=None):
        """
        Update message engagement metrics
        
        Args:
            whatsapp_message_id: WhatsApp message ID
            engagement_type: 'delivered', 'read', 'replied', 'clicked'
            timestamp: ISO timestamp (defaults to now)
            reply_text: Text of the reply (for 'replied' engagement)
        """
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Map engagement type to column
            column_map = {
                'delivered': 'delivered_at',
                'read': 'read_at',
                'replied': 'replied_at',
                'clicked': 'clicked_at'
            }
            
            column = column_map.get(engagement_type)
            if not column:
                return
            
            # Build update query
            if engagement_type == 'replied' and reply_text:
                # Update both replied_at and reply_text
                cursor.execute(f'''
                    UPDATE messages 
                    SET {column} = ?, reply_text = ?
                    WHERE whatsapp_message_id = ? AND {column} IS NULL
                ''', (timestamp, reply_text, whatsapp_message_id))
            else:
                # Update only the timestamp
                cursor.execute(f'''
                    UPDATE messages 
                    SET {column} = ?
                    WHERE whatsapp_message_id = ? AND {column} IS NULL
                ''', (timestamp, whatsapp_message_id))
            
            rows_updated = cursor.rowcount
            
            # Get campaign_id for updating counts
            campaign_id = None
            if rows_updated > 0:
                cursor.execute('''
                    SELECT campaign_id FROM messages 
                    WHERE whatsapp_message_id = ?
                ''', (whatsapp_message_id,))
                
                result = cursor.fetchone()
                if result:
                    campaign_id = result['campaign_id']
            else:
                # Fallback: Find most recent message to update (for testing without message IDs)
                # This helps track engagement even if message ID wasn't stored
                cursor.execute(f'''
                    SELECT id, campaign_id FROM messages 
                    WHERE {column} IS NULL 
                    AND sent_at > datetime('now', '-1 hour')
                    AND status = 'sent'
                    ORDER BY sent_at DESC
                    LIMIT 1
                ''')
                
                result = cursor.fetchone()
                if result:
                    message_id = result['id']
                    campaign_id = result['campaign_id']
                    
                    # Update this message
                    cursor.execute(f'''
                        UPDATE messages 
                        SET {column} = ?
                        WHERE id = ?
                    ''', (timestamp, message_id))
                    
                    rows_updated = 1
            
            # Update campaign counts if we found a campaign
            if campaign_id and rows_updated > 0:
                count_column = engagement_type + '_count'
                
                cursor.execute(f'''
                    UPDATE campaigns 
                    SET {count_column} = {count_column} + 1
                    WHERE id = ?
                ''', (campaign_id,))
                
                logger.info(f"✅ Updated {engagement_type} count for campaign {campaign_id}")
    
    def get_campaign_messages(self, campaign_id, limit=None):
        """Get messages for a campaign"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if limit:
                cursor.execute('''
                    SELECT * FROM messages 
                    WHERE campaign_id = ? 
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (campaign_id, limit))
            else:
                cursor.execute('''
                    SELECT * FROM messages 
                    WHERE campaign_id = ? 
                    ORDER BY created_at DESC
                ''', (campaign_id,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    # Activity Log Methods
    def log_activity(self, user_id, username, action, details=None, ip_address=None):
        """Log user activity"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO activity_log (user_id, username, action, details, ip_address)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, action, details, ip_address))
    
    def get_user_activity(self, user_id, limit=50):
        """Get user activity log"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM activity_log 
                WHERE user_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (user_id, limit))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_all_activity(self, limit=100):
        """Get all activity (admin view)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM activity_log 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    # Customer Methods
    def add_or_update_customer(self, user_id, customer_data):
        """Add or update a customer from Shopify"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # INSERT OR IGNORE creates the row if the shopify_id doesn't exist yet.
            # The subsequent UPDATE then sets all fields (including user_id) so that
            # records previously owned by a different user_id are reassigned to the
            # current user on re-sync.
            cursor.execute('''
                INSERT OR IGNORE INTO customers (user_id, shopify_id, first_name, last_name,
                                                 email, phone, total_spent, orders_count,
                                                 state, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, customer_data['shopify_id'], customer_data['first_name'],
                  customer_data['last_name'], customer_data['email'],
                  customer_data['phone'], customer_data['total_spent'],
                  customer_data['orders_count'], customer_data['state'],
                  customer_data['tags']))

            cursor.execute('''
                UPDATE customers
                SET user_id = ?, first_name = ?, last_name = ?, email = ?, phone = ?,
                    total_spent = ?, orders_count = ?, state = ?, tags = ?,
                    updated_at = ?
                WHERE shopify_id = ?
            ''', (user_id, customer_data['first_name'], customer_data['last_name'],
                  customer_data['email'], customer_data['phone'],
                  customer_data['total_spent'], customer_data['orders_count'],
                  customer_data['state'], customer_data['tags'],
                  datetime.now().isoformat(), customer_data['shopify_id']))
    
    def get_last_shopify_created_at(self, user_id):
        """Return the most recent shopify_created_at for this user, or None if none stored."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT MAX(shopify_created_at) FROM customers WHERE user_id = ? AND shopify_created_at IS NOT NULL',
                (user_id,)
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def bulk_add_or_update_customers(self, user_id, customers_data):
        """Upsert a list of customers in a single transaction (much faster than one-by-one)."""
        if not customers_data:
            return
        now = datetime.now().isoformat()
        insert_rows = []
        update_rows = []
        for c in customers_data:
            insert_rows.append((
                user_id, c['shopify_id'], c['first_name'], c['last_name'],
                c['email'], c['phone'], c['total_spent'], c['orders_count'],
                c['state'], c['tags'], c.get('created_at') or None
            ))
            update_rows.append((
                user_id, c['first_name'], c['last_name'], c['email'], c['phone'],
                c['total_spent'], c['orders_count'], c['state'], c['tags'],
                c.get('created_at') or None, now, c['shopify_id']
            ))
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany('''
                INSERT OR IGNORE INTO customers (user_id, shopify_id, first_name, last_name,
                                                 email, phone, total_spent, orders_count,
                                                 state, tags, shopify_created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', insert_rows)
            cursor.executemany('''
                UPDATE customers
                SET user_id = ?, first_name = ?, last_name = ?, email = ?, phone = ?,
                    total_spent = ?, orders_count = ?, state = ?, tags = ?,
                    shopify_created_at = ?, updated_at = ?
                WHERE shopify_id = ?
            ''', update_rows)

    def get_all_customers(self, user_id, filters=None):
        """Get all customers with optional filters"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = 'SELECT * FROM customers WHERE user_id = ?'
            params = [user_id]
            
            if filters:
                if filters.get('has_phone'):
                    query += ' AND phone IS NOT NULL AND phone != ""'
                
                # Order value filters
                if filters.get('min_order_value') is not None:
                    query += ' AND total_spent >= ?'
                    params.append(filters['min_order_value'])
                if filters.get('max_order_value') is not None:
                    query += ' AND total_spent <= ?'
                    params.append(filters['max_order_value'])
                
                # Number of orders filters
                if filters.get('min_orders') is not None:
                    query += ' AND orders_count >= ?'
                    params.append(filters['min_orders'])
                if filters.get('max_orders') is not None:
                    query += ' AND orders_count <= ?'
                    params.append(filters['max_orders'])
                
                # Predefined segment types
                if filters.get('segment_type'):
                    segment_type = filters['segment_type']
                    if segment_type == 'engaged_last_7_days':
                        cutoff = " strftime('%Y-%m-%dT%H:%M:%S', 'now', '-7 days') "
                        query += (
                            f" AND (last_message_sent >= {cutoff}"
                            f" OR last_message_read >= {cutoff}"
                            f" OR last_message_replied >= {cutoff})"
                        )
                    elif segment_type == 'not_engaged_last_7_days':
                        cutoff = " strftime('%Y-%m-%dT%H:%M:%S', 'now', '-7 days') "
                        query += (
                            f" AND (last_message_sent IS NULL OR last_message_sent < {cutoff})"
                        )
                    elif segment_type == 'no_message_sent':
                        query += ' AND (last_message_sent IS NULL OR messages_sent_count = 0)'
                    elif segment_type == 'high_value':
                        query += ' AND total_spent > 1000'
                    elif segment_type == 'has_orders':
                        query += ' AND orders_count > 0'
                    elif segment_type == 'replied':
                        query += ' AND messages_replied_count > 0'
                    elif segment_type.startswith('custom_'):
                        # Handle custom segments
                        segment_id = segment_type.replace('custom_', '')
                        segment = self.get_segment_by_id(segment_id)
                        if segment and segment.get('conditions'):
                            conditions = json.loads(segment['conditions'])
                            if conditions.get('min_order_value') is not None:
                                query += ' AND total_spent >= ?'
                                params.append(conditions['min_order_value'])
                            if conditions.get('max_order_value') is not None:
                                query += ' AND total_spent <= ?'
                                params.append(conditions['max_order_value'])
                            if conditions.get('min_orders') is not None:
                                query += ' AND orders_count >= ?'
                                params.append(conditions['min_orders'])
                            if conditions.get('max_orders') is not None:
                                query += ' AND orders_count <= ?'
                                params.append(conditions['max_orders'])
            
            query += ' ORDER BY updated_at DESC'
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_customer_by_phone(self, phone):
        """Get customer by phone number"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM customers WHERE phone = ?', (phone,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def update_customer_message_stats(self, phone, stat_type):
        """Update customer message statistics"""
        if not phone:
            return
        # WhatsApp webhook sends recipient_id without '+'; customers are stored with '+'
        if not phone.startswith('+'):
            phone = '+' + phone

        with self.get_connection() as conn:
            cursor = conn.cursor()

            if stat_type == 'sent':
                cursor.execute('''
                    UPDATE customers 
                    SET messages_sent_count = messages_sent_count + 1,
                        last_message_sent = ?
                    WHERE phone = ?
                ''', (datetime.now().isoformat(), phone))
            elif stat_type == 'read':
                cursor.execute('''
                    UPDATE customers 
                    SET messages_read_count = messages_read_count + 1,
                        last_message_read = ?
                    WHERE phone = ?
                ''', (datetime.now().isoformat(), phone))
            elif stat_type == 'replied':
                cursor.execute('''
                    UPDATE customers 
                    SET messages_replied_count = messages_replied_count + 1,
                        last_message_replied = ?
                    WHERE phone = ?
                ''', (datetime.now().isoformat(), phone))
    
    def create_segment(self, user_id, segment_name, segment_type, conditions=None):
        """Create a customer segment"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO customer_segments (user_id, segment_name, segment_type, conditions)
                VALUES (?, ?, ?, ?)
            ''', (user_id, segment_name, segment_type, json.dumps(conditions) if conditions else None))
            return cursor.lastrowid
    
    def get_user_segments(self, user_id):
        """Get all segments for a user"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM customer_segments 
                WHERE user_id = ? 
                ORDER BY created_at DESC
            ''', (user_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_segment_by_id(self, segment_id):
        """Get segment by ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM customer_segments WHERE id = ?', (segment_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def delete_segment(self, segment_id, user_id):
        """Delete a custom segment"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM customer_segments 
                WHERE id = ? AND user_id = ?
            ''', (segment_id, user_id))
            return cursor.rowcount > 0
    
    def get_segment_customers(self, user_id, segment_type):
        """Get customers for a specific segment"""
        filters = {'segment_type': segment_type}
        return self.get_all_customers(user_id, filters)
    
    # Abandoned Cart Methods
    def add_abandoned_cart(self, user_id, cart_data):
        """Add or update abandoned cart"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO abandoned_carts
                (user_id, shopify_cart_id, customer_id, customer_name, customer_email, customer_phone,
                 cart_token, cart_items, total_price, currency, abandoned_at, cart_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                cart_data.get('id'),
                cart_data.get('customer_id'),
                cart_data.get('first_name'),
                cart_data.get('email'),
                cart_data.get('phone'),
                cart_data.get('token'),
                json.dumps(cart_data.get('line_items', [])),
                cart_data.get('total_price'),
                cart_data.get('currency'),
                datetime.now().isoformat(),
                cart_data.get('abandoned_checkout_url')
            ))
            return cursor.lastrowid
    
    def get_unsent_cart_reminders(self, user_id):
        """Get abandoned carts that haven't received reminders"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM abandoned_carts 
                WHERE user_id = ? 
                AND reminder_sent = 0 
                AND recovered = 0
                AND customer_phone IS NOT NULL 
                AND customer_phone != ""
                ORDER BY abandoned_at DESC
            ''', (user_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def mark_cart_reminder_sent(self, cart_id):
        """Mark cart reminder as sent"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE abandoned_carts 
                SET reminder_sent = 1, reminder_sent_at = ?
                WHERE id = ?
            ''', (datetime.now().isoformat(), cart_id))
    
    def mark_cart_recovered(self, shopify_cart_id):
        """Mark cart as recovered (by Shopify cart token)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE abandoned_carts
                SET recovered = 1, recovered_at = ?
                WHERE shopify_cart_id = ?
            ''', (datetime.now().isoformat(), shopify_cart_id))

    def mark_cart_recovered_by_id(self, cart_id):
        """Mark cart as recovered by internal DB id (fallback when token doesn't match)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE abandoned_carts
                SET recovered = 1, recovered_at = ?
                WHERE id = ?
            ''', (datetime.now().isoformat(), cart_id))

    def get_abandoned_carts_ready_for_reminder(self, user_id, delay_hours=1):
        """Get carts past the delay threshold that haven't been reminded yet"""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(hours=delay_hours)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM abandoned_carts
                WHERE user_id = ?
                  AND reminder_sent = 0
                  AND recovered = 0
                  AND customer_phone IS NOT NULL AND customer_phone != ''
                  AND abandoned_at <= ?
                ORDER BY abandoned_at ASC
            ''', (user_id, cutoff.isoformat()))
            return [dict(row) for row in cursor.fetchall()]

    # Order Methods
    def add_order(self, user_id, order_data):
        """Add or update order"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO shopify_orders 
                (user_id, shopify_order_id, order_number, customer_id, customer_email, 
                 customer_phone, total_price, currency, financial_status, fulfillment_status, order_items)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                order_data.get('id'),
                order_data.get('order_number'),
                order_data.get('customer', {}).get('id'),
                order_data.get('email'),
                order_data.get('phone') or order_data.get('customer', {}).get('phone'),
                order_data.get('total_price'),
                order_data.get('currency'),
                order_data.get('financial_status'),
                order_data.get('fulfillment_status'),
                json.dumps(order_data.get('line_items', []))
            ))
            return cursor.lastrowid
    
    def get_unsent_order_confirmations(self, user_id):
        """Get orders that haven't received confirmation"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM shopify_orders 
                WHERE user_id = ? 
                AND confirmation_sent = 0
                AND customer_phone IS NOT NULL 
                AND customer_phone != ""
                ORDER BY created_at DESC
            ''', (user_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def mark_order_confirmation_sent(self, order_id):
        """Mark order confirmation as sent"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE shopify_orders
                SET confirmation_sent = 1, confirmation_sent_at = ?
                WHERE id = ?
            ''', (datetime.now().isoformat(), order_id))

    def mark_fulfillment_sent(self, order_id):
        """Mark fulfillment notification as sent"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE shopify_orders
                SET fulfillment_sent = 1, fulfillment_sent_at = ?
                WHERE id = ?
            ''', (datetime.now().isoformat(), order_id))

    def get_order_by_shopify_id(self, shopify_order_id):
        """Get order row by Shopify order ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM shopify_orders WHERE shopify_order_id = ?',
                           (str(shopify_order_id),))
            row = cursor.fetchone()
            return dict(row) if row else None

    def mark_order_fulfillment_received(self, shopify_order_id):
        """Update fulfillment_status to 'fulfilled' for an existing order"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE shopify_orders
                SET fulfillment_status = 'fulfilled', updated_at = ?
                WHERE shopify_order_id = ?
            ''', (datetime.now().isoformat(), str(shopify_order_id)))

    def save_order_tracking_url(self, shopify_order_id, tracking_url,
                                tracking_number=None, tracking_company=None,
                                order_status_url=None):
        """Save tracking URL/number/courier for an order (used by /track/<order_ref>).

        All fields but tracking_url are optional so older callers keep working;
        when omitted the existing stored values are left untouched.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE shopify_orders
                SET tracking_url = ?,
                    tracking_number = COALESCE(?, tracking_number),
                    tracking_company = COALESCE(?, tracking_company),
                    order_status_url = COALESCE(?, order_status_url),
                    updated_at = ?
                WHERE shopify_order_id = ?
            ''', (tracking_url, tracking_number, tracking_company, order_status_url,
                  datetime.now().isoformat(), str(shopify_order_id)))

    def save_order_status_url(self, shopify_order_id, order_status_url):
        """Store Shopify's customer-facing order status URL (set from orders/create)."""
        if not order_status_url:
            return
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE shopify_orders
                SET order_status_url = ?, updated_at = ?
                WHERE shopify_order_id = ?
            ''', (order_status_url, datetime.now().isoformat(), str(shopify_order_id)))

    def get_order_tracking_url(self, order_ref):
        """Get tracking info by order number (for /track/<order_ref>).
        order_ref is the raw order number digits (e.g. '4123' for order #F14123).
        Returns dict with tracking_url, tracking_number, tracking_company, order_number.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT shopify_order_id, tracking_url, tracking_number, tracking_company,
                       order_status_url, order_number
                FROM shopify_orders
                WHERE order_number = ? OR order_number = ? OR shopify_order_id = ?
                ORDER BY updated_at DESC LIMIT 1
            ''', (order_ref, '#' + order_ref, order_ref))
            row = cursor.fetchone()
            if row:
                return {
                    'shopify_order_id': row['shopify_order_id'],
                    'tracking_url': row['tracking_url'],
                    'tracking_number': row['tracking_number'],
                    'tracking_company': row['tracking_company'],
                    'order_status_url': row['order_status_url'],
                    'order_number': row['order_number'],
                }
            return None

    # Automation Settings Methods
    def get_automation_settings(self, user_id):
        """Return automation settings dict keyed by event_type, with defaults."""
        defaults = {
            'order_confirmation': {
                'enabled': 0, 'template_name': '', 'template_language': 'en_US',
                'delay_hours': 0, 'extra_data': {}
            },
            'fulfillment': {
                'enabled': 0, 'template_name': '', 'template_language': 'en_US',
                'delay_hours': 0, 'extra_data': {}
            },
            'abandoned_cart': {
                'enabled': 0, 'template_name': '', 'template_language': 'en_US',
                'delay_hours': 1,
                'extra_data': {'discount_code': '', 'recovery_url': ''}
            },
        }
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM automation_settings WHERE user_id = ?', (user_id,))
            rows = cursor.fetchall()
        for row in rows:
            row = dict(row)
            et = row['event_type']
            if et in defaults:
                try:
                    extra = json.loads(row.get('extra_data') or '{}')
                except Exception:
                    extra = {}
                defaults[et] = {
                    'enabled': int(row['enabled']),
                    'template_name': row['template_name'] or '',
                    'template_language': row['template_language'] or 'en_US',
                    'delay_hours': int(row['delay_hours']) if row['delay_hours'] else
                                   (1 if et == 'abandoned_cart' else 0),
                    'extra_data': extra,
                }
        return defaults

    def save_automation_setting(self, user_id, event_type, enabled, template_name,
                                template_language, delay_hours=0, extra_data=None):
        """Upsert a single automation setting row."""
        now = datetime.now().isoformat()
        extra_json = json.dumps(extra_data or {})
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO automation_settings
                    (user_id, event_type, enabled, template_name, template_language,
                     delay_hours, extra_data, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, event_type, int(enabled), template_name, template_language,
                  delay_hours, extra_json, now, now))
            cursor.execute('''
                UPDATE automation_settings
                SET enabled = ?, template_name = ?, template_language = ?,
                    delay_hours = ?, extra_data = ?, updated_at = ?
                WHERE user_id = ? AND event_type = ?
            ''', (int(enabled), template_name, template_language, delay_hours,
                  extra_json, now, user_id, event_type))

    # Template Usage Methods
    def track_template_usage(self, user_id, username, template_name):
        """Track template usage"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if already tracked
            cursor.execute('''
                SELECT id, times_used FROM template_usage 
                WHERE user_id = ? AND template_name = ?
            ''', (user_id, template_name))
            
            row = cursor.fetchone()
            
            if row:
                # Update existing
                cursor.execute('''
                    UPDATE template_usage 
                    SET times_used = times_used + 1, last_used = ?
                    WHERE id = ?
                ''', (datetime.now().isoformat(), row['id']))
            else:
                # Insert new
                cursor.execute('''
                    INSERT INTO template_usage (user_id, username, template_name)
                    VALUES (?, ?, ?)
                ''', (user_id, username, template_name))
    
    def get_template_stats(self, user_id=None):
        """Get template usage statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if user_id:
                cursor.execute('''
                    SELECT template_name, times_used, last_used
                    FROM template_usage 
                    WHERE user_id = ?
                    ORDER BY times_used DESC
                ''', (user_id,))
            else:
                cursor.execute('''
                    SELECT template_name, SUM(times_used) as times_used, MAX(last_used) as last_used
                    FROM template_usage 
                    GROUP BY template_name
                    ORDER BY times_used DESC
                ''')
            
            return [dict(row) for row in cursor.fetchall()]
    
    # Session Methods
    def create_session(self, user_id, username, ip_address=None, user_agent=None):
        """Create user session"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_sessions (user_id, username, ip_address, user_agent)
                VALUES (?, ?, ?, ?)
            ''', (user_id, username, ip_address, user_agent))
            
            return cursor.lastrowid
    
    def close_session(self, session_id):
        """Close user session"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE user_sessions 
                SET logout_time = ?
                WHERE id = ?
            ''', (datetime.now().isoformat(), session_id))
    
    def get_user_sessions(self, user_id, limit=20):
        """Get user sessions"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM user_sessions 
                WHERE user_id = ? 
                ORDER BY login_time DESC 
                LIMIT ?
            ''', (user_id, limit))
            
            return [dict(row) for row in cursor.fetchall()]
    
    # Analytics Methods
    def get_dashboard_stats(self, user_id=None):
        """Get dashboard statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            stats = {}
            
            # Total campaigns
            if user_id:
                cursor.execute('SELECT COUNT(*) as count FROM campaigns WHERE user_id = ?', (user_id,))
            else:
                cursor.execute('SELECT COUNT(*) as count FROM campaigns')
            stats['total_campaigns'] = cursor.fetchone()['count']
            
            # Total messages (exclude queued/pending — only count messages that were
            # actually dispatched to the WhatsApp API)
            if user_id:
                cursor.execute(
                    "SELECT COUNT(*) as count FROM messages WHERE user_id = ? "
                    "AND status IN ('sent','delivered','read','replied','failed')",
                    (user_id,)
                )
            else:
                cursor.execute(
                    "SELECT COUNT(*) as count FROM messages "
                    "WHERE status IN ('sent','delivered','read','replied','failed')"
                )
            stats['total_messages'] = cursor.fetchone()['count']

            # Total failed messages directly from the messages table (source of truth,
            # cross-checks the aggregated campaign.failed_count)
            if user_id:
                cursor.execute(
                    "SELECT COUNT(*) as count FROM messages WHERE user_id = ? AND status = 'failed'",
                    (user_id,)
                )
            else:
                cursor.execute(
                    "SELECT COUNT(*) as count FROM messages WHERE status = 'failed'"
                )
            stats['total_failed_messages'] = cursor.fetchone()['count']
            
            # Success rate
            if user_id:
                cursor.execute('''
                    SELECT 
                        SUM(success_count) as success,
                        SUM(failed_count) as failed
                    FROM campaigns WHERE user_id = ?
                ''', (user_id,))
            else:
                cursor.execute('''
                    SELECT 
                        SUM(success_count) as success,
                        SUM(failed_count) as failed
                    FROM campaigns
                ''')
            
            row = cursor.fetchone()
            success = row['success'] or 0
            failed = row['failed'] or 0
            total = success + failed
            stats['success_rate'] = (success / total * 100) if total > 0 else 0
            stats['success_count'] = success
            stats['failed_count'] = failed
            
            # Engagement metrics
            if user_id:
                cursor.execute('''
                    SELECT 
                        SUM(delivered_count) as delivered,
                        SUM(read_count) as read,
                        SUM(replied_count) as replied,
                        SUM(clicked_count) as clicked
                    FROM campaigns WHERE user_id = ?
                ''', (user_id,))
            else:
                cursor.execute('''
                    SELECT 
                        SUM(delivered_count) as delivered,
                        SUM(read_count) as read,
                        SUM(replied_count) as replied,
                        SUM(clicked_count) as clicked
                    FROM campaigns
                ''')
            
            row = cursor.fetchone()
            stats['delivered_count'] = row['delivered'] or 0
            stats['read_count'] = row['read'] or 0
            stats['replied_count'] = row['replied'] or 0
            stats['clicked_count'] = row['clicked'] or 0
            
            # Calculate engagement rates
            if success > 0:
                stats['delivery_rate'] = (stats['delivered_count'] / success * 100)
                stats['read_rate'] = (stats['read_count'] / success * 100)
                stats['reply_rate'] = (stats['replied_count'] / success * 100)
                stats['click_rate'] = (stats['clicked_count'] / success * 100)
            else:
                stats['delivery_rate'] = 0
                stats['read_rate'] = 0
                stats['reply_rate'] = 0
                stats['click_rate'] = 0
            
            # Active campaigns
            if user_id:
                cursor.execute('''
                    SELECT COUNT(*) as count FROM campaigns 
                    WHERE user_id = ? AND status = 'running'
                ''', (user_id,))
            else:
                cursor.execute('''
                    SELECT COUNT(*) as count FROM campaigns 
                    WHERE status = 'running'
                ''')
            stats['active_campaigns'] = cursor.fetchone()['count']
            
            # Scheduled campaigns
            if user_id:
                cursor.execute('''
                    SELECT COUNT(*) as count FROM campaigns 
                    WHERE user_id = ? AND status = 'scheduled'
                ''', (user_id,))
            else:
                cursor.execute('''
                    SELECT COUNT(*) as count FROM campaigns 
                    WHERE status = 'scheduled'
                ''')
            stats['scheduled_campaigns'] = cursor.fetchone()['count']
            
            # Recent activity
            if user_id:
                cursor.execute('''
                    SELECT COUNT(*) as count FROM activity_log 
                    WHERE user_id = ? AND timestamp > datetime('now', '-24 hours')
                ''', (user_id,))
            else:
                cursor.execute('''
                    SELECT COUNT(*) as count FROM activity_log 
                    WHERE timestamp > datetime('now', '-24 hours')
                ''')
            stats['recent_activity'] = cursor.fetchone()['count']
            
            return stats
    
    def get_campaign_stats_by_date(self, user_id=None, days=30):
        """Get campaign statistics by date"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if user_id:
                cursor.execute('''
                    SELECT 
                        DATE(created_at) as date,
                        COUNT(*) as count,
                        SUM(recipient_count) as recipients,
                        SUM(success_count) as success,
                        SUM(failed_count) as failed
                    FROM campaigns 
                    WHERE user_id = ? AND created_at > datetime('now', ? || ' days')
                    GROUP BY DATE(created_at)
                    ORDER BY date DESC
                ''', (user_id, -days))
            else:
                cursor.execute('''
                    SELECT 
                        DATE(created_at) as date,
                        COUNT(*) as count,
                        SUM(recipient_count) as recipients,
                        SUM(success_count) as success,
                        SUM(failed_count) as failed
                    FROM campaigns 
                    WHERE created_at > datetime('now', ? || ' days')
                    GROUP BY DATE(created_at)
                    ORDER BY date DESC
                ''', (-days,))
            
            return [dict(row) for row in cursor.fetchall()]
