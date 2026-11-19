import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# GROUP_CHAT_ID может быть числом (-100...) или строкой
_group_id_raw = os.getenv("GROUP_CHAT_ID", "").strip()
try:
    GROUP_CHAT_ID = int(_group_id_raw) if _group_id_raw else None
except ValueError:
    GROUP_CHAT_ID = None

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не указан в файле .env!")
