"""
Debug script to check engagement tracking
"""

import sqlite3
from datetime import datetime

DB_PATH = 'whatsapp_dashboard.db'

def check_database():
    """Check database state for engagement tracking"""
    
    print("=" * 60)
    print("ENGAGEMENT TRACKING DEBUG")
    print("=" * 60)
    print()
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Check campaigns table
        print("📊 CAMPAIGNS:")
        cursor.execute('''
            SELECT id, campaign_name, success_count, failed_count, 
                   delivered_count, read_count, replied_count, clicked_count,
                   created_at
            FROM campaigns 
            ORDER BY created_at DESC 
            LIMIT 5
        ''')
        
        campaigns = cursor.fetchall()
        if campaigns:
            for campaign in campaigns:
                print(f"\nCampaign #{campaign['id']}: {campaign['campaign_name']}")
                print(f"  Sent: {campaign['success_count']}")
                print(f"  Failed: {campaign['failed_count']}")
                print(f"  Delivered: {campaign['delivered_count']}")
                print(f"  Read: {campaign['read_count']}")
                print(f"  Replied: {campaign['replied_count']}")
                print(f"  Clicked: {campaign['clicked_count']}")
                print(f"  Created: {campaign['created_at'][:19]}")
        else:
            print("  ⚠️ No campaigns found!")
        
        print("\n" + "-" * 60)
        
        # Check messages table
        print("\n📨 MESSAGES:")
        cursor.execute('''
            SELECT id, phone_number, status, sent_at, delivered_at, read_at,
                   replied_at, whatsapp_message_id, created_at
            FROM messages 
            ORDER BY created_at DESC 
            LIMIT 10
        ''')
        
        messages = cursor.fetchall()
        if messages:
            for msg in messages:
                print(f"\nMessage #{msg['id']} to {msg['phone_number']}")
                print(f"  Status: {msg['status']}")
                print(f"  Sent: {msg['sent_at'][:19] if msg['sent_at'] else 'Not sent'}")
                print(f"  Delivered: {msg['delivered_at'][:19] if msg['delivered_at'] else 'No'}")
                print(f"  Read: {msg['read_at'][:19] if msg['read_at'] else 'No'}")
                print(f"  Replied: {msg['replied_at'][:19] if msg['replied_at'] else 'No'}")
                print(f"  WhatsApp ID: {msg['whatsapp_message_id'] or 'None'}")
        else:
            print("  ⚠️ No messages found!")
        
        print("\n" + "-" * 60)
        
        # Check table structure
        print("\n🔧 CAMPAIGNS TABLE STRUCTURE:")
        cursor.execute("PRAGMA table_info(campaigns)")
        columns = [col[1] for col in cursor.fetchall()]
        print(f"  Columns: {', '.join(columns)}")
        
        engagement_columns = ['delivered_count', 'read_count', 'replied_count', 'clicked_count']
        for col in engagement_columns:
            if col in columns:
                print(f"  ✅ {col} exists")
            else:
                print(f"  ❌ {col} MISSING!")
        
        print("\n🔧 MESSAGES TABLE STRUCTURE:")
        cursor.execute("PRAGMA table_info(messages)")
        columns = [col[1] for col in cursor.fetchall()]
        print(f"  Columns: {', '.join(columns)}")
        
        engagement_columns = ['delivered_at', 'read_at', 'replied_at', 'clicked_at', 'whatsapp_message_id']
        for col in engagement_columns:
            if col in columns:
                print(f"  ✅ {col} exists")
            else:
                print(f"  ❌ {col} MISSING!")
        
        print("\n" + "=" * 60)
        
        # Summary
        print("\n📈 SUMMARY:")
        
        cursor.execute("SELECT COUNT(*) as count FROM campaigns")
        campaign_count = cursor.fetchone()['count']
        print(f"  Total Campaigns: {campaign_count}")
        
        cursor.execute("SELECT COUNT(*) as count FROM messages")
        message_count = cursor.fetchone()['count']
        print(f"  Total Messages: {message_count}")
        
        cursor.execute("SELECT COUNT(*) as count FROM messages WHERE sent_at IS NOT NULL")
        sent_count = cursor.fetchone()['count']
        print(f"  Sent Messages: {sent_count}")
        
        cursor.execute("SELECT COUNT(*) as count FROM messages WHERE delivered_at IS NOT NULL")
        delivered_count = cursor.fetchone()['count']
        print(f"  Delivered Messages: {delivered_count}")
        
        cursor.execute("SELECT COUNT(*) as count FROM messages WHERE read_at IS NOT NULL")
        read_count = cursor.fetchone()['count']
        print(f"  Read Messages: {read_count}")
        
        cursor.execute("SELECT COUNT(*) as count FROM messages WHERE replied_at IS NOT NULL")
        replied_count = cursor.fetchone()['count']
        print(f"  Replied Messages: {replied_count}")
        
        print("\n" + "=" * 60)
        
        # Recommendations
        print("\n💡 RECOMMENDATIONS:")
        
        if message_count == 0:
            print("  ⚠️ No messages in database!")
            print("  → Send messages through the dashboard to create message records")
        
        if sent_count == 0 and message_count > 0:
            print("  ⚠️ Messages exist but none marked as sent!")
            print("  → Check message queue and rate limiter")
        
        if delivered_count == 0 and sent_count > 0:
            print("  ⚠️ Messages sent but none delivered!")
            print("  → Check webhook is receiving delivery updates")
            print("  → Check whatsapp_message_id is being stored")
        
        if campaign_count > 0:
            cursor.execute('''
                SELECT SUM(delivered_count) as total 
                FROM campaigns
            ''')
            result = cursor.fetchone()
            total = result['total'] if result['total'] else 0
            
            if total == 0:
                print("  ⚠️ Campaigns exist but no delivered_count!")
                print("  → Webhook might not be updating campaign counts")
        
        print("\n" + "=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        conn.close()

if __name__ == "__main__":
    check_database()
