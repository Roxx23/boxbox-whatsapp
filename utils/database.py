# Database models for campaign tracking and analytics
import sqlite3
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager

logger = logging.getLogger(__name__)


def _now_utc():
    """UTC timestamp as a naive ISO string, matching SQLite's strftime('now').

    Flow timestamps must use this (not datetime.now().isoformat(), which is
    server-local IST) because flow_engine.py compares them against UTC.
    """
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')


def _parse_legacy_ts(ts):
    """Normalize a `messages.replied_at` value to an ISO string, or None if it
    can't be parsed. That column is usually ISO (from datetime.now().isoformat()),
    but process_incoming_message() also writes the raw WhatsApp webhook
    `timestamp` verbatim when the webhook supplies one — a Unix epoch string like
    '1730000000', not ISO. Every reader that sorts, compares, or displays this
    column needs to go through this first; get_last_inbound_message_at() avoids
    the column entirely instead, since it gates a send decision."""
    if not ts:
        return None
    try:
        datetime.fromisoformat(ts)
        return ts
    except (ValueError, TypeError):
        pass
    try:
        return datetime.fromtimestamp(int(ts)).isoformat()
    except (ValueError, TypeError, OSError, OverflowError):
        return None


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

            # Inbox: full two-way message log (inbound customer replies + manual outbound
            # sends from the inbox UI). Separate from `messages` (campaign sends, which only
            # ever record ONE reply per outbound message via reply_text/replied_at) so no
            # incoming message is ever dropped or overwritten.
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS inbox_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    message_text TEXT,
                    message_type TEXT,
                    whatsapp_message_id TEXT,
                    status TEXT DEFAULT 'received',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_inbox_messages_phone
                ON inbox_messages(user_id, phone, created_at)
            ''')

            # Flows tables
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS flows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    trigger_type TEXT NOT NULL,
                    status TEXT DEFAULT 'draft',
                    canvas_data TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS flow_steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    flow_id INTEGER NOT NULL,
                    step_key TEXT NOT NULL,
                    step_type TEXT NOT NULL,
                    config TEXT NOT NULL DEFAULT '{}',
                    next_yes TEXT,
                    next_no TEXT,
                    UNIQUE(flow_id, step_key),
                    FOREIGN KEY (flow_id) REFERENCES flows(id) ON DELETE CASCADE
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS flow_participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    flow_id INTEGER NOT NULL,
                    phone TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    current_step_key TEXT,
                    next_action_at TEXT,
                    context TEXT DEFAULT '{}',
                    enrolled_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT,
                    exit_reason TEXT,
                    UNIQUE(flow_id, phone),
                    FOREIGN KEY (flow_id) REFERENCES flows(id) ON DELETE CASCADE
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS flow_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    flow_id INTEGER NOT NULL,
                    flow_participant_id INTEGER NOT NULL,
                    step_key TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    whatsapp_message_id TEXT,
                    status TEXT DEFAULT 'sent',
                    sent_at TEXT,
                    delivered_at TEXT,
                    read_at TEXT,
                    replied_at TEXT,
                    reply_text TEXT,
                    FOREIGN KEY (flow_id) REFERENCES flows(id),
                    FOREIGN KEY (flow_participant_id) REFERENCES flow_participants(id)
                )
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_flow_messages_wamid
                ON flow_messages(whatsapp_message_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_flow_participants_active
                ON flow_participants(status, next_action_at)
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
                'ALTER TABLE flows ADD COLUMN allow_reenroll INTEGER DEFAULT 1',
                'ALTER TABLE inbox_messages ADD COLUMN read_at TEXT',
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
    
    # Inbox (two-way messaging)

    def add_inbox_message(self, user_id, phone, direction, message_text,
                           message_type=None, whatsapp_message_id=None, status=None):
        """Log one inbound or outbound message for the two-way inbox.

        This is the complete, going-forward record of every message exchanged with a
        customer — unlike `messages.reply_text`, which only ever captures the FIRST
        reply to a given outbound campaign message (a second reply to the same message
        is silently dropped by update_message_engagement's `WHERE ... IS NULL` guard).
        """
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''INSERT INTO inbox_messages
                   (user_id, phone, direction, message_text, message_type,
                    whatsapp_message_id, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (user_id, phone, direction, message_text, message_type,
                 whatsapp_message_id, status or ('received' if direction == 'inbound' else 'sent'), now)
            )
            return cursor.lastrowid

    def get_inbox_conversations(self, user_id, limit=200):
        """One row per phone number, most recent message first. Primary source is
        inbox_messages (complete, going forward); for a phone with no inbox_messages
        rows yet, falls back to the legacy messages.reply_text so customers who replied
        before this feature shipped still show up in the list."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''SELECT phone, message_text, direction, created_at
                   FROM inbox_messages WHERE user_id = ?''',
                (user_id,)
            )
            latest = {}
            for row in cursor.fetchall():
                phone = row['phone']
                if phone not in latest or row['created_at'] > latest[phone]['created_at']:
                    latest[phone] = dict(row)

            cursor.execute(
                '''SELECT phone_number as phone, reply_text as message_text, replied_at as created_at
                   FROM messages WHERE user_id = ? AND reply_text IS NOT NULL AND replied_at IS NOT NULL''',
                (user_id,)
            )
            for row in cursor.fetchall():
                phone = row['phone']
                if phone not in latest:
                    d = dict(row)
                    d['direction'] = 'inbound'
                    d['created_at'] = _parse_legacy_ts(d['created_at'])
                    latest[phone] = d

            cursor.execute(
                '''SELECT DISTINCT phone FROM inbox_messages
                   WHERE user_id = ? AND direction = 'inbound' AND read_at IS NULL''',
                (user_id,)
            )
            unread_phones_clean = {row['phone'].lstrip('+') for row in cursor.fetchall()}

            phones = list(latest.keys())
            customers_by_phone = {}
            if phones:
                placeholders = ','.join('?' * len(phones))
                phones_clean = [p.lstrip('+') for p in phones]
                cursor.execute(
                    f'''SELECT phone, first_name, last_name FROM customers
                        WHERE user_id = ? AND (phone IN ({placeholders}) OR phone IN ({placeholders}))''',
                    [user_id] + phones + phones_clean
                )
                for row in cursor.fetchall():
                    customers_by_phone[row['phone']] = dict(row)

        results = []
        for phone, row in latest.items():
            customer = customers_by_phone.get(phone) or customers_by_phone.get(phone.lstrip('+'))
            results.append({
                'phone': phone,
                'customer_name': f"{customer['first_name'] or ''} {customer['last_name'] or ''}".strip() if customer else None,
                'last_message_text': row['message_text'],
                'last_message_direction': row['direction'],
                'last_message_at': row['created_at'],
                'has_unread': phone.lstrip('+') in unread_phones_clean,
            })
        results.sort(key=lambda r: r['last_message_at'] or '', reverse=True)
        return results[:limit]

    def get_inbox_thread(self, user_id, phone):
        """Chronological two-way thread for one customer: outbound campaign sends
        (messages table) merged with every inbox_messages row (inbound customer
        replies + manual outbound sends from the inbox UI), plus legacy replies
        recorded before this feature shipped (messages.reply_text)."""
        phone_clean = phone.lstrip('+')
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''SELECT message_content as text, template_name, sent_at as ts
                   FROM messages
                   WHERE user_id = ? AND (phone_number = ? OR phone_number = ?) AND sent_at IS NOT NULL''',
                (user_id, phone, phone_clean)
            )
            thread = []
            for row in cursor.fetchall():
                d = dict(row)
                thread.append({
                    'direction': 'outbound',
                    'text': d['text'] or (f"[Template: {d['template_name']}]" if d['template_name'] else ''),
                    'ts': d['ts'],
                    'source': 'campaign',
                })

            cursor.execute(
                '''SELECT direction, message_text as text, message_type, created_at as ts
                   FROM inbox_messages
                   WHERE user_id = ? AND (phone = ? OR phone = ?)
                   ORDER BY created_at ASC''',
                (user_id, phone, phone_clean)
            )
            inbox_rows = [dict(row) for row in cursor.fetchall()]
            for d in inbox_rows:
                thread.append({
                    'direction': d['direction'],
                    'text': d['text'],
                    'ts': d['ts'],
                    'source': 'inbox',
                })

            cursor.execute(
                '''SELECT reply_text as text, replied_at as ts
                   FROM messages
                   WHERE user_id = ? AND (phone_number = ? OR phone_number = ?)
                   AND reply_text IS NOT NULL AND replied_at IS NOT NULL''',
                (user_id, phone, phone_clean)
            )
            legacy_replies = [dict(row) for row in cursor.fetchall()]

        # messages.replied_at is usually ISO, but process_incoming_message() also
        # writes WhatsApp's raw webhook timestamp (a Unix epoch string) verbatim
        # when one is supplied — normalize before any comparison, sort, or display
        # ever touches it.
        for d in legacy_replies:
            d['ts'] = _parse_legacy_ts(d['ts'])

        # Dedup: a reply captured by BOTH this legacy column AND the (going-forward)
        # inbox_messages log — same webhook call writes both — would otherwise show
        # as two near-identical bubbles. inbox_messages.created_at and
        # messages.replied_at are written moments apart in the same request, so
        # treat any inbound inbox_messages row within 60s of a legacy reply as the
        # same event and skip the legacy one. A legacy reply whose timestamp can't
        # be parsed at all, or has no nearby inbox_messages row, is shown — false
        # negatives here (an extra bubble) are far less bad than hiding a real reply.
        inbound_times = []
        for d in inbox_rows:
            if d['direction'] != 'inbound' or not d['ts']:
                continue
            try:
                inbound_times.append(datetime.fromisoformat(d['ts']))
            except Exception:
                continue

        for d in legacy_replies:
            is_duplicate = False
            try:
                legacy_dt = datetime.fromisoformat(d['ts'])
                is_duplicate = any(abs((legacy_dt - t).total_seconds()) <= 60 for t in inbound_times)
            except Exception:
                pass
            if not is_duplicate:
                thread.append({
                    'direction': 'inbound',
                    'text': d['text'],
                    'ts': d['ts'],
                    'source': 'legacy',
                })

        thread.sort(key=lambda m: m['ts'] or '')
        return thread

    def get_last_inbound_message_at(self, user_id, phone):
        """Most recent inbound inbox_messages timestamp for this phone, or None.
        Deliberately does NOT consult the legacy messages.replied_at column — that
        field's timestamp source (raw webhook value) isn't reliably ISO-formatted,
        and this value gates whether a free-form WhatsApp reply is allowed, so a
        clean, self-controlled timestamp is safer than a best-effort one. WhatsApp's
        own API is still the final authority and will reject sends outside the
        24h window regardless of this check."""
        phone_clean = phone.lstrip('+')
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''SELECT MAX(created_at) as ts FROM inbox_messages
                   WHERE user_id = ? AND direction = 'inbound' AND (phone = ? OR phone = ?)''',
                (user_id, phone, phone_clean)
            )
            row = cursor.fetchone()
            return row['ts'] if row else None

    def has_unread_inbox_messages(self, user_id):
        """Cheap boolean check: any inbound inbox_messages row for this user
        not yet marked read. Used to drive the nav unread dot on every page,
        so this must stay an EXISTS/LIMIT 1, not a full count."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''SELECT 1 FROM inbox_messages
                   WHERE user_id = ? AND direction = 'inbound' AND read_at IS NULL
                   LIMIT 1''',
                (user_id,)
            )
            return cursor.fetchone() is not None

    def mark_inbox_thread_read(self, user_id, phone):
        """Mark all inbound messages in this thread as read."""
        phone_clean = phone.lstrip('+')
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''UPDATE inbox_messages SET read_at = ?
                   WHERE user_id = ? AND direction = 'inbound' AND read_at IS NULL
                   AND (phone = ? OR phone = ?)''',
                (datetime.now().isoformat(), user_id, phone, phone_clean)
            )

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
        """Log user activity.

        Writes an explicit datetime.now().isoformat() timestamp rather than
        relying on the column's DEFAULT CURRENT_TIMESTAMP -- SQLite's
        CURRENT_TIMESTAMP is hardcoded UTC regardless of the OS timezone
        (verified: it doesn't shift even on a server whose OS clock is
        genuinely IST), unlike every other server-local timestamp in this
        app written via datetime.now(). Matches the write pattern already
        used for inbox_messages/messages so the ist_time display filter
        (reformat-only, no arithmetic) is safe to apply here too.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO activity_log (user_id, username, action, details, ip_address, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, username, action, details, ip_address, datetime.now().isoformat()))
    
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
            
            # Recent activity. activity_log.timestamp is now written as
            # server-local time (see log_activity()), so the comparison must
            # use SQLite's 'localtime' modifier too -- plain datetime('now', ...)
            # is UTC and would skew this by the server's UTC offset (was
            # harmless before since both sides were UTC; not anymore).
            if user_id:
                cursor.execute('''
                    SELECT COUNT(*) as count FROM activity_log
                    WHERE user_id = ? AND timestamp > datetime('now', '-24 hours', 'localtime')
                ''', (user_id,))
            else:
                cursor.execute('''
                    SELECT COUNT(*) as count FROM activity_log
                    WHERE timestamp > datetime('now', '-24 hours', 'localtime')
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

    # ── Flow Methods ──────────────────────────────────────────────────────────

    def create_flow(self, user_id, name, trigger_type):
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO flows (user_id, name, trigger_type, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
                (user_id, name, trigger_type, now, now)
            )
            return cursor.lastrowid

    def get_flow(self, flow_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM flows WHERE id = ?', (flow_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_user_flows(self, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM flows WHERE user_id = ? ORDER BY created_at DESC',
                (user_id,)
            )
            return [dict(r) for r in cursor.fetchall()]

    def update_flow(self, flow_id, name=None, status=None, canvas_data=None, allow_reenroll=None):
        updates, params = [], []
        if name is not None:
            updates.append('name = ?'); params.append(name)
        if status is not None:
            updates.append('status = ?'); params.append(status)
        if canvas_data is not None:
            updates.append('canvas_data = ?'); params.append(canvas_data)
        if allow_reenroll is not None:
            updates.append('allow_reenroll = ?'); params.append(1 if allow_reenroll else 0)
        if not updates:
            return
        updates.append('updated_at = ?'); params.append(datetime.now().isoformat())
        params.append(flow_id)
        with self.get_connection() as conn:
            conn.cursor().execute(
                f'UPDATE flows SET {", ".join(updates)} WHERE id = ?', params
            )

    def delete_flow(self, flow_id):
        with self.get_connection() as conn:
            conn.cursor().execute('DELETE FROM flows WHERE id = ?', (flow_id,))

    def get_active_flows_by_trigger(self, user_id, trigger_type):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM flows WHERE user_id = ? AND trigger_type = ? AND status = 'active'",
                (user_id, trigger_type)
            )
            return [dict(r) for r in cursor.fetchall()]

    # Flow Steps

    def replace_flow_steps(self, flow_id, steps):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM flow_steps WHERE flow_id = ?', (flow_id,))
            for s in steps:
                cursor.execute(
                    '''INSERT INTO flow_steps (flow_id, step_key, step_type, config, next_yes, next_no)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (flow_id, s['step_key'], s['step_type'],
                     json.dumps(s.get('config', {})),
                     s.get('next_yes'), s.get('next_no'))
                )

    def get_flow_steps(self, flow_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM flow_steps WHERE flow_id = ?', (flow_id,))
            return [dict(r) for r in cursor.fetchall()]

    def get_flow_step(self, flow_id, step_key):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM flow_steps WHERE flow_id = ? AND step_key = ?',
                (flow_id, str(step_key))
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    # Flow Participants

    def enroll_flow_participant(self, flow_id, phone, context_dict, first_step_key, next_action_at):
        """`next_action_at` is caller-computed (see flow_engine._next_action_at_for_entering)
        so that landing directly on a 'wait' step at enrollment time delays correctly,
        the same way advancing onto a 'wait' step mid-flow does."""
        now = _now_utc()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id, status FROM flow_participants WHERE flow_id = ? AND phone = ?',
                (flow_id, phone)
            )
            existing = cursor.fetchone()
            if existing:
                if existing['status'] in ('completed', 'exited', 'error'):
                    cursor.execute('SELECT allow_reenroll FROM flows WHERE id = ?', (flow_id,))
                    flow_row = cursor.fetchone()
                    if flow_row is not None and flow_row['allow_reenroll'] == 0:
                        # Flow owner disabled re-enrollment — leave participant as-is
                        return None
                    # Re-enroll: reset to active with fresh context and step
                    cursor.execute(
                        '''UPDATE flow_participants
                           SET status='active', current_step_key=?, next_action_at=?,
                               context=?, enrolled_at=?, completed_at=NULL, exit_reason=NULL
                           WHERE id=?''',
                        (str(first_step_key), next_action_at, json.dumps(context_dict), now, existing['id'])
                    )
                    return existing['id']
                else:
                    # Already active in this flow — skip to avoid double-processing
                    return None
            cursor.execute(
                '''INSERT INTO flow_participants
                   (flow_id, phone, current_step_key, next_action_at, context, enrolled_at)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (flow_id, phone, str(first_step_key), next_action_at, json.dumps(context_dict), now)
            )
            return cursor.lastrowid

    def get_due_flow_participants(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT * FROM flow_participants
                   WHERE status = 'active' AND next_action_at <= strftime('%Y-%m-%dT%H:%M:%S', 'now')
                   ORDER BY next_action_at ASC LIMIT 100"""
            )
            return [dict(r) for r in cursor.fetchall()]

    def update_participant_step(self, participant_id, step_key, next_action_at):
        with self.get_connection() as conn:
            conn.cursor().execute(
                'UPDATE flow_participants SET current_step_key = ?, next_action_at = ? WHERE id = ?',
                (str(step_key), next_action_at, participant_id)
            )

    def update_participant_next_action(self, participant_id, next_action_at):
        with self.get_connection() as conn:
            conn.cursor().execute(
                'UPDATE flow_participants SET next_action_at = ? WHERE id = ?',
                (next_action_at, participant_id)
            )

    def complete_participant(self, participant_id):
        with self.get_connection() as conn:
            conn.cursor().execute(
                "UPDATE flow_participants SET status = 'completed', completed_at = ? WHERE id = ?",
                (_now_utc(), participant_id)
            )

    def exit_participant(self, participant_id, reason=None):
        with self.get_connection() as conn:
            conn.cursor().execute(
                "UPDATE flow_participants SET status = 'exited', exit_reason = ?, completed_at = ? WHERE id = ?",
                (reason, _now_utc(), participant_id)
            )

    def set_participant_error(self, participant_id):
        with self.get_connection() as conn:
            conn.cursor().execute(
                "UPDATE flow_participants SET status = 'error' WHERE id = ?",
                (participant_id,)
            )

    def get_flow_participants(self, flow_id, status=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute(
                    'SELECT * FROM flow_participants WHERE flow_id = ? AND status = ? ORDER BY enrolled_at DESC',
                    (flow_id, status)
                )
            else:
                cursor.execute(
                    'SELECT * FROM flow_participants WHERE flow_id = ? ORDER BY enrolled_at DESC',
                    (flow_id,)
                )
            return [dict(r) for r in cursor.fetchall()]

    def get_flow_participant_by_id(self, participant_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM flow_participants WHERE id = ?', (participant_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    # Flow Messages

    def add_flow_message(self, flow_id, participant_id, step_key, phone, wamid=None):
        now = _now_utc()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''INSERT INTO flow_messages
                   (flow_id, flow_participant_id, step_key, phone, whatsapp_message_id, sent_at)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (flow_id, participant_id, str(step_key), phone, wamid, now)
            )
            return cursor.lastrowid

    def get_last_flow_message(self, participant_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM flow_messages WHERE flow_participant_id = ? ORDER BY sent_at DESC LIMIT 1',
                (participant_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_flow_message_by_wamid(self, whatsapp_message_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM flow_messages WHERE whatsapp_message_id = ?',
                (whatsapp_message_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_flow_message_status(self, whatsapp_message_id, field, value):
        allowed = {'delivered_at', 'read_at', 'replied_at', 'reply_text', 'status'}
        if field not in allowed:
            return
        with self.get_connection() as conn:
            conn.cursor().execute(
                f'UPDATE flow_messages SET {field} = ? WHERE whatsapp_message_id = ?',
                (value, whatsapp_message_id)
            )

    def get_flow_participant_counts(self, flow_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''SELECT status, COUNT(*) as cnt FROM flow_participants
                   WHERE flow_id = ? GROUP BY status''',
                (flow_id,)
            )
            return {r['status']: r['cnt'] for r in cursor.fetchall()}

    def get_flow_step_stats(self, flow_id):
        """Per-step analytics for the flow editor stats panel.

        'currently_at' = active participants sitting at this step right now.
        'passed_through' = participants whose current position is this step or any
        step reachable from it (found via BFS over next_yes/next_no) — since a
        participant can only reach a downstream step by having passed through this
        one first. For send_message steps this is cross-checked against the exact
        flow_messages log (sent/delivered/read/replied), which is the authoritative
        source for those rates.
        """
        steps = self.get_flow_steps(flow_id)
        step_by_key = {s['step_key']: s for s in steps}

        def reachable_from(start_key):
            seen = set()
            stack = [start_key]
            while stack:
                k = stack.pop()
                if k is None or k in seen or k not in step_by_key:
                    continue
                seen.add(k)
                s = step_by_key[k]
                stack.append(s.get('next_yes'))
                stack.append(s.get('next_no'))
            return seen

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT status, current_step_key FROM flow_participants WHERE flow_id = ?',
                (flow_id,)
            )
            participants = cursor.fetchall()

            cursor.execute(
                '''SELECT step_key, COUNT(*) as sent,
                          SUM(CASE WHEN delivered_at IS NOT NULL THEN 1 ELSE 0 END) as delivered,
                          SUM(CASE WHEN read_at IS NOT NULL THEN 1 ELSE 0 END) as read_ct,
                          SUM(CASE WHEN replied_at IS NOT NULL THEN 1 ELSE 0 END) as replied
                   FROM flow_messages WHERE flow_id = ? GROUP BY step_key''',
                (flow_id,)
            )
            msg_stats = {r['step_key']: dict(r) for r in cursor.fetchall()}

        position_counts = {}
        active_counts = {}
        for p in participants:
            key = p['current_step_key']
            position_counts[key] = position_counts.get(key, 0) + 1
            if p['status'] == 'active':
                active_counts[key] = active_counts.get(key, 0) + 1

        result = []
        for s in steps:
            if s['step_type'] == 'trigger':
                continue
            key = s['step_key']
            descendants = reachable_from(key)
            passed_through = sum(cnt for pos, cnt in position_counts.items() if pos in descendants)
            row = {
                'step_key': key,
                'step_type': s['step_type'],
                'currently_at': active_counts.get(key, 0),
                'passed_through': passed_through,
            }
            if s['step_type'] == 'send_message':
                m = msg_stats.get(key, {'sent': 0, 'delivered': 0, 'read_ct': 0, 'replied': 0})
                sent = m['sent'] or 0
                row['sent'] = sent
                row['delivered_rate'] = round(100 * (m['delivered'] or 0) / sent, 1) if sent else 0
                row['read_rate'] = round(100 * (m['read_ct'] or 0) / sent, 1) if sent else 0
                row['reply_rate'] = round(100 * (m['replied'] or 0) / sent, 1) if sent else 0
            result.append(row)
        return result

    def customer_placed_order_since(self, phone, since_iso):
        """since_iso is 'YYYY-MM-DDTHH:MM:SS' (from _now_utc). shopify_orders.created_at
        defaults to SQLite's CURRENT_TIMESTAMP, which uses a space separator
        ('YYYY-MM-DD HH:MM:SS') — space sorts before 'T' as a string, so comparing
        them directly makes every same-day order look older than it is. Normalise
        the separator before comparing."""
        phone_clean = phone.lstrip('+')
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''SELECT id FROM shopify_orders
                   WHERE (customer_phone = ? OR customer_phone = ?)
                   AND replace(created_at, ' ', 'T') > ? LIMIT 1''',
                (phone, phone_clean, since_iso)
            )
            return cursor.fetchone() is not None
