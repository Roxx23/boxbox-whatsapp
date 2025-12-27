"""
Database Migration Script
Adds engagement tracking columns to existing database
"""

import sqlite3
from datetime import datetime

DB_PATH = 'whatsapp_dashboard.db'

def migrate_database():
    """Add new engagement tracking columns to existing tables"""
    
    print("🔄 Starting database migration...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(campaigns)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Add columns to campaigns table
        new_campaign_columns = {
            'delivered_count': 'INTEGER DEFAULT 0',
            'read_count': 'INTEGER DEFAULT 0',
            'replied_count': 'INTEGER DEFAULT 0',
            'clicked_count': 'INTEGER DEFAULT 0'
        }
        
        for col_name, col_type in new_campaign_columns.items():
            if col_name not in columns:
                print(f"  Adding {col_name} to campaigns table...")
                cursor.execute(f"ALTER TABLE campaigns ADD COLUMN {col_name} {col_type}")
                print(f"  ✅ Added {col_name}")
            else:
                print(f"  ⏭️  {col_name} already exists")
        
        # Check messages table
        cursor.execute("PRAGMA table_info(messages)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Add columns to messages table
        new_message_columns = {
            'delivered_at': 'TEXT',
            'read_at': 'TEXT',
            'replied_at': 'TEXT',
            'clicked_at': 'TEXT',
            'whatsapp_message_id': 'TEXT'
        }
        
        for col_name, col_type in new_message_columns.items():
            if col_name not in columns:
                print(f"  Adding {col_name} to messages table...")
                cursor.execute(f"ALTER TABLE messages ADD COLUMN {col_name} {col_type}")
                print(f"  ✅ Added {col_name}")
            else:
                print(f"  ⏭️  {col_name} already exists")
        
        conn.commit()
        print("\n✅ Migration completed successfully!")
        
        # Verify the changes
        print("\n📊 Verifying campaigns table structure:")
        cursor.execute("PRAGMA table_info(campaigns)")
        for col in cursor.fetchall():
            print(f"  - {col[1]}: {col[2]}")
        
        print("\n📊 Verifying messages table structure:")
        cursor.execute("PRAGMA table_info(messages)")
        for col in cursor.fetchall():
            print(f"  - {col[1]}: {col[2]}")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        conn.rollback()
        raise
    
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("DATABASE MIGRATION SCRIPT")
    print("Adding engagement tracking columns")
    print("=" * 60)
    print()
    
    try:
        migrate_database()
        print("\n" + "=" * 60)
        print("✅ MIGRATION COMPLETE!")
        print("You can now restart your Flask app and use analytics")
        print("=" * 60)
    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ MIGRATION FAILED!")
        print(f"Error: {e}")
        print("=" * 60)
