# Database models for campaign tracking and analytics
import sqlite3
import json
import logging
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class Database:
    """Database manager for campaign tracking"""
    
    def __init__(self, db_path='whatsapp_dashboard.db'):
        self.db_path = db_path
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
    
    def get_user_campaigns(self, user_id, limit=50):
        """Get campaigns for a user"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM campaigns 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (user_id, limit))
            
            return [dict(row) for row in cursor.fetchall()]
    
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
                   message_content=None, template_name=None, status='pending'):
        """Add a message to campaign"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO messages (campaign_id, user_id, phone_number, recipient_name,
                                    message_content, template_name, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (campaign_id, user_id, phone_number, recipient_name, 
                  message_content, template_name, status))
            
            return cursor.lastrowid
    
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
    
    def get_campaign_messages(self, campaign_id, limit=1000):
        """Get messages for a campaign"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM messages 
                WHERE campaign_id = ? 
                ORDER BY created_at DESC
                LIMIT ?
            ''', (campaign_id, limit))
            
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
            
            # Total messages
            if user_id:
                cursor.execute('SELECT COUNT(*) as count FROM messages WHERE user_id = ?', (user_id,))
            else:
                cursor.execute('SELECT COUNT(*) as count FROM messages')
            stats['total_messages'] = cursor.fetchone()['count']
            
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
