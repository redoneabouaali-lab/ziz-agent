"""
ZIZ Agent — SQLite → PostgreSQL migration script.
Run THIS from the old app directory (where factures.db lives).
Creates .env automatically from old SQLite settings.
"""
import os, sys, sqlite3, json
from datetime import date

# ── Paths ──
OLD_DB = os.path.expandvars(r"%LOCALAPPDATA%\ziz_echeances\factures.db")
NEW_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(NEW_DIR, ".env")

if not os.path.exists(OLD_DB):
    print(f"❌ Old DB not found: {OLD_DB}")
    sys.exit(1)

print(f"📂 Source: {OLD_DB}")
print(f"📂 Target: {NEW_DIR}")

# ── 1. Extract settings → .env ──
conn = sqlite3.connect(OLD_DB)
settings = dict(conn.execute("SELECT key, value FROM settings").fetchall())
conn.close()

env_map = {
    "tg_token": "TG_TOKEN",
    "nv_api_key": "NV_API_KEY",
    "groq_api_key": "GROQ_API_KEY",
    "wa_url": "WA_URL",
    "wa_api_key": "WA_API_KEY",
    "wa_session": "WA_SESSION",
    "wa_phone": "WA_PHONE",
    "smtp_host": "SMTP_HOST",
    "smtp_port": "SMTP_PORT",
    "smtp_user": "SMTP_USER",
    "smtp_pass": "SMTP_PASS",
    "email_to": "EMAIL_TO",
    "api_port": "API_PORT",
    "companies": "COMPANIES",
    "current_company": "CURRENT_COMPANY",
    "n8n_webhook_url": "N8N_WEBHOOK_URL",
}

with open(ENV_PATH, "w") as f:
    f.write("# ZIZ Agent — Auto-generated from old app\n")
    f.write(f"# Generated: {date.today().isoformat()}\n\n")
    f.write("# --- Database (PostgreSQL) ---\n")
    f.write("DB_HOST=postgres\nDB_PORT=5432\nDB_NAME=ziz_agent\nDB_USER=ziz\n")
    f.write("DB_PASSWORD=" + settings.get("db_password", "changeme") + "\n\n")

    for old_key, new_key in env_map.items():
        val = settings.get(old_key, "")
        if val:
            f.write(f"{new_key}={val}\n")
    f.write(f"\n# --- n8n ---\n")
    f.write(f"N8N_REMINDER_URL=https://n8nv1.abouaaliahmed.com/webhook/reminder\n")

print(f"✅ .env created with {len(settings)} old settings extracted")

# ── 2. Migration instructions ──
print("""
┌─────────────────────────────────────────────────────────────┐
│  NEXT STEPS:                                                │
│                                                             │
│  1. Set up PostgreSQL on your VPS or locally                │
│  2. Edit .env → set DB_PASSWORD                             │
│  3. docker compose up -d                                    │
│                                                             │
│  The bot auto-creates tables on first start.                │
│                                                             │
│  To migrate old invoice data to PostgreSQL:                 │
│  python migrations/migrate_data.py                          │
└─────────────────────────────────────────────────────────────┘
""")
