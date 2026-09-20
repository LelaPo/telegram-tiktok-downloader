"""Configuration loader and environment validator."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load variables from .env file into environment
load_dotenv()

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    sys.exit("CRITICAL: TELEGRAM_BOT_TOKEN is not set in environment or .env file.")

# Whitelisted User IDs
raw_user_ids = os.getenv("ALLOWED_USER_IDS", "")
ALLOWED_USER_IDS: set[int] = set()
for uid_token in raw_user_ids.split(","):
    cleaned = uid_token.strip()
    if cleaned.isdigit():
        ALLOWED_USER_IDS.add(int(cleaned))

if not ALLOWED_USER_IDS:
    sys.exit(
        "CRITICAL: ALLOWED_USER_IDS is empty. Provide at least one numeric Telegram user ID."
    )

# Temporary Storage Directory
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "/tmp/yt_audio_bot")).resolve()
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
