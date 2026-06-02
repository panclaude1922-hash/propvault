"""
config.py — загрузка переменных окружения
"""

import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
WEBAPP_URL: str = os.getenv("WEBAPP_URL", "https://your-app.vercel.app")

_raw_admins = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: list[int] = [
    int(x.strip()) for x in _raw_admins.split(",") if x.strip().isdigit()
]

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан в .env файле!")
