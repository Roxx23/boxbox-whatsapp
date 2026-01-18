import os
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
LOG_FILE = os.getenv("LOG_FILE", "logs.csv")

# Shopify Integration
SHOPIFY_SHOP_NAME = os.getenv("SHOPIFY_SHOP_NAME")  # e.g., "your-store"
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")
