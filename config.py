import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

XUI_HOST = os.getenv(
    "XUI_HOST",
    "https://127.0.0.1:1337/ZoxJbyRPdLe5t4y243",
).rstrip("/")

XUI_API_TOKEN = os.getenv("XUI_API_TOKEN", "")

TRIAL_HOURS = int(os.getenv("TRIAL_HOURS", "12"))
TRIAL_LIMIT = int(os.getenv("TRIAL_LIMIT", "4"))

DATABASE_PATH = os.getenv(
    "DATABASE_PATH",
    "/opt/vpn-bot/bot.db",
)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

if not ADMIN_ID:
    raise RuntimeError("ADMIN_ID is not set")

if not XUI_API_TOKEN:
    raise RuntimeError("XUI_API_TOKEN is not set")
