import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)
load_dotenv()

# Telegram Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

raw_keys = os.getenv("GEMINI_API_KEYS", "") or os.getenv("GEMINI_API_KEY", "")
parsed_keys = [k.strip() for k in raw_keys.split(",") if k.strip()]

GEMINI_KEYS = parsed_keys

ADMIN_ID = os.getenv("ADMIN_ID", "")
ARCHIVE_CHANNEL_ID = os.getenv("ARCHIVE_CHANNEL_ID", "")
REQUEST_DELAY_SECONDS = float(os.getenv("REQUEST_DELAY_SECONDS", "15.0"))
