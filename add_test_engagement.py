"""
Manual test to add engagement data for testing
"""

import sqlite3
from datetime import datetime

DB_PATH = 'whatsapp_dashboard.db'

def add_test_engagement():
    """Add test engagement data to verify dashboard display"""
    
    print("=" * 60)
    print("ADDING TEST ENGAGEMENT DATA")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Find latest campaign
        cursor.execute('SELECT id FROM campaigns ORDER BY id DESC LIMIT 1')
        result = cursor.fetchone()
        
        if not result:
            print("❌ No campaigns found! Create a campaign first.")
            return
        
        campaign_id = result[0]
        print(f"\n✅ Found campaign ID: {campaign_id}")
        
        # Update campaign with test engagement data
        print("\n📊 Adding test engagement metrics...")
        
        cursor.execute('''
            UPDATE campaigns 
            SET delivered_count = 10,
                read_count = 8,
                replied_count = 3,
                clicked_count = 1
            WHERE id = ?
        ''', (campaign_id,))
        
        conn.commit()
        
        print(f"  ✅ Delivered: 10")
        print(f"  ✅ Read: 8")
        print(f"  ✅ Replied: 3")
        print(f"  ✅ Clicked: 1")
        
        # Verify
        cursor.execute('''
            SELECT delivered_count, read_count, replied_count, clicked_count
            FROM campaigns
            WHERE id = ?
        ''', (campaign_id,))
        
        result = cursor.fetchone()
        print(f"\n✅ VERIFIED:")
        print(f"  Delivered: {result[0]}")
        print(f"  Read: {result[1]}")
        print(f"  Replied: {result[2]}")
        print(f"  Clicked: {result[3]}")
        
        print("\n" + "=" * 60)
        print("✅ TEST DATA ADDED!")
        print("Now refresh your analytics page to see the metrics!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        conn.rollback()
        import traceback
        traceback.print_exc()
    
    finally:
        conn.close()

if __name__ == "__main__":
    add_test_engagement()
