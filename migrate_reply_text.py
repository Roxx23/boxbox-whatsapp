"""
Migration: Add reply_text column to messages table
"""
import sqlite3
import os

DB_PATH = 'whatsapp_dashboard.db'

def migrate():
    """Add reply_text column to messages table if it doesn't exist"""
    
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(messages)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'reply_text' in columns:
            print("✅ Column 'reply_text' already exists")
        else:
            print("➕ Adding 'reply_text' column to messages table...")
            cursor.execute("ALTER TABLE messages ADD COLUMN reply_text TEXT")
            conn.commit()
            print("✅ Migration completed successfully!")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    print("\n" + "="*50)
    print("📊 Database Migration: Add reply_text column")
    print("="*50 + "\n")
    migrate()
    print("\n" + "="*50 + "\n")
