import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Gemini API Keys (comma-separated for multi-key rotation to avoid limits)
# Example: GEMINI_API_KEYS="key1,key2,key3"
raw_keys = os.getenv("GEMINI_API_KEYS", "") or os.getenv("GEMINI_API_KEY", "")
GEMINI_KEYS = [k.strip() for k in raw_keys.split(",") if k.strip()]

# Admin ID for errors / monitoring
ADMIN_ID = os.getenv("ADMIN_ID", "")

# Channel for storing generated files copy (optional)
ARCHIVE_CHANNEL_ID = os.getenv("ARCHIVE_CHANNEL_ID", "")

# Rate limiting delay between Gemini requests (seconds)
REQUEST_DELAY_SECONDS = float(os.getenv("REQUEST_DELAY_SECONDS", "4.0"))
