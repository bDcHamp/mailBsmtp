"""
Configuration management for Marketing SMTP Mailer.
Loads settings from .env file or environment variables.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def load_env_file(env_path: Path = None):
    """Zero-dependency .env loader."""
    if env_path is None:
        env_path = BASE_DIR / ".env"
    if not env_path.is_file():
        return

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception:
        pass


# Load .env at module import
load_env_file()


def get_bool(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


class Config:
    # SMTP Server Settings (Ideal for Webmail cPanel/DirectAdmin/Custom Domain)
    SMTP_HOST = os.getenv("SMTP_HOST", "mail.example.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
    SMTP_USER = os.getenv("SMTP_USER", "reminders@example.com")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    
    # Auto-detect SSL/TLS defaults based on port unless explicitly defined
    SMTP_USE_SSL = get_bool("SMTP_USE_SSL", SMTP_PORT == 465)
    SMTP_USE_TLS = get_bool("SMTP_USE_TLS", SMTP_PORT == 587)
    
    # Sender Profile
    SENDER_NAME = os.getenv("SENDER_NAME", "Marketing Operations Team")
    SENDER_EMAIL = os.getenv("SENDER_EMAIL", SMTP_USER)
    
    # Scheduling & Quotas
    # Default: 100 emails per client per 24 hours
    DAILY_CAP_PER_CLIENT = int(os.getenv("DAILY_CAP_PER_CLIENT", "100"))
    WINDOW_HOURS = float(os.getenv("WINDOW_HOURS", "24.0"))
    
    # Pacing interval in seconds: 24h / 100 emails = 864s (~14.4 minutes) per client
    # Can be overridden via MIN_INTERVAL_SECONDS for testing or custom pacing
    _calculated_interval = (WINDOW_HOURS * 3600.0) / max(1, DAILY_CAP_PER_CLIENT)
    MIN_INTERVAL_SECONDS = float(os.getenv("MIN_INTERVAL_SECONDS", str(_calculated_interval)))
    
    # Global delay between any two outgoing emails to prevent hitting webmail rate limits
    GLOBAL_DISPATCH_DELAY = float(os.getenv("GLOBAL_DISPATCH_DELAY", "2.0"))
    
    # Email Subject
    EMAIL_SUBJECT = os.getenv("EMAIL_SUBJECT", "Work Progress & Action Items Reminder")
    
    # Paths
    DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "mailer.db")))
    CLIENTS_CSV_PATH = Path(os.getenv("CLIENTS_CSV_PATH", str(BASE_DIR / "data" / "clients.csv")))
    CLIENTS_JSON_PATH = Path(os.getenv("CLIENTS_JSON_PATH", str(BASE_DIR / "data" / "clients.json")))
    HTML_TEMPLATE_PATH = Path(os.getenv("HTML_TEMPLATE_PATH", str(BASE_DIR / "templates" / "reminder.html")))
    TEXT_TEMPLATE_PATH = Path(os.getenv("TEXT_TEMPLATE_PATH", str(BASE_DIR / "templates" / "reminder.txt")))

