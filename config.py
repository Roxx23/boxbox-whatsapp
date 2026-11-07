import os
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
LOG_FILE = os.getenv("LOG_FILE", "logs.csv")

# Shopify Integration
SHOPIFY_SHOP_NAME = os.getenv("SHOPIFY_SHOP_NAME")  # e.g., "your-store"
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")  # static fallback; see utils/shopify_auth.py
SHOPIFY_CLIENT_ID = os.getenv("SHOPIFY_CLIENT_ID")          # Dev Dashboard app: token via client-credentials grant
SHOPIFY_CLIENT_SECRET = os.getenv("SHOPIFY_CLIENT_SECRET")
