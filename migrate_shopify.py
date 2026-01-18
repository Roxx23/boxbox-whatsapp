"""
Database Migration Script for Shopify Integration
Adds customers and customer_segments tables
"""

from utils.database import Database
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    """Run database migration"""
    try:
        logger.info("🔄 Starting database migration...")
        
        # Initialize database (will create new tables if they don't exist)
        db = Database()
        
        logger.info("✅ Database migration completed successfully!")
        logger.info("📊 New tables created:")
        logger.info("   - customers")
        logger.info("   - customer_segments")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    success = migrate()
    if success:
        print("\n✅ Migration completed! You can now use Shopify integration.")
        print("📝 Next steps:")
        print("   1. Add Shopify credentials to your .env file:")
        print("      SHOPIFY_SHOP_NAME=your-store")
        print("      SHOPIFY_ACCESS_TOKEN=shpat_xxxxx")
        print("   2. Restart your Flask application")
        print("   3. Go to Customers page and click 'Sync Shopify'")
    else:
        print("\n❌ Migration failed. Check the logs above for details.")
