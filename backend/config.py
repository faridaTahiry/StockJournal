from pathlib import Path

from dotenv import load_dotenv
import os

# Load backend/.env regardless of process cwd (e.g. uvicorn from repo root).
load_dotenv(Path(__file__).resolve().parent / ".env")
DATABASE_URL = os.getenv("DATABASE_URL")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ALERT_EMAIL_FROM = os.getenv("ALERT_EMAIL_FROM")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO")
# Always copied on alert emails, in addition to ALERT_EMAIL_TO (deduped). Override with env to change or set empty to disable.
ALERT_EMAIL_ALWAYS_TO = "farida.tahiry.13@gmail.com"
ALERT_SMTP_HOST = os.getenv("ALERT_SMTP_HOST", "smtp.gmail.com")
ALERT_SMTP_PORT = int(os.getenv("ALERT_SMTP_PORT", "587"))
ALERT_SMTP_USER = os.getenv("ALERT_SMTP_USER")
ALERT_SMTP_PASS = os.getenv("ALERT_SMTP_PASS")