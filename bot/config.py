"""ZIZ Agent — Configuration from environment / .env file"""
import os
from dotenv import load_dotenv

load_dotenv()
# Also load from persistent storage volume (Coolify / Docker)
load_dotenv('/data/.env')


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


# ── Database ──
DB_HOST = _env("DB_HOST", "localhost")
DB_PORT = int(_env("DB_PORT", "5432"))
DB_NAME = _env("DB_NAME", "ziz_agent")
DB_USER = _env("DB_USER", "ziz")
DB_PASSWORD = _env("DB_PASSWORD", "change_me")

DSN = f"host={DB_HOST} port={DB_PORT} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}"

# ── Telegram ──
TG_TOKEN = _env("TG_TOKEN")

# ── AI / LLM ──
LLM_PROVIDER = _env("LLM_PROVIDER", "gemini")  # gemini or nvidia
GEMINI_API_KEY = _env("GEMINI_API_KEY")
GEMINI_MODEL = _env("GEMINI_MODEL", "gemini-2.0-flash")
NV_API_KEY = _env("NV_API_KEY")  # kept as fallback
GROQ_API_KEY = _env("GROQ_API_KEY")
NV_MODEL = _env("NV_MODEL", "meta/llama-3.3-70b-instruct")
NV_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

# ── WhatsApp (OpenWA) ──
WA_URL = _env("WA_URL", "").rstrip("/")
WA_API_KEY = _env("WA_API_KEY")
WA_SESSION = _env("WA_SESSION", "default")
WA_PHONE = _env("WA_PHONE", "")

# ── Email ──
SMTP_HOST = _env("SMTP_HOST")
SMTP_PORT = int(_env("SMTP_PORT", "587"))
SMTP_USER = _env("SMTP_USER")
SMTP_PASS = _env("SMTP_PASS")
EMAIL_TO = _env("EMAIL_TO")

# ── Bot ──
API_PORT = int(_env("API_PORT", "5679"))
COMPANIES = [c.strip() for c in _env("COMPANIES", "ZIZPHYTOSERVICE,HB ADRAR").split(",")]
CURRENT_COMPANY = _env("CURRENT_COMPANY", "ZIZPHYTOSERVICE")

# ── n8n ──
N8N_WEBHOOK_URL = _env("N8N_WEBHOOK_URL", "").rstrip("/")
N8N_REMINDER_URL = _env("N8N_REMINDER_URL", "").rstrip("/")
