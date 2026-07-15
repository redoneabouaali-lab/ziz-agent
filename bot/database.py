"""ZIZ Agent — PostgreSQL database layer"""
import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from datetime import date, datetime
from typing import Optional, List, Dict, Any

from bot.config import DSN


# ── Connection pool ──
@contextmanager
def get_db():
    """Yield a database connection (context manager, auto-closes)."""
    conn = psycopg2.connect(DSN)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def get_cursor():
    """Yield a dictionary cursor."""
    conn = psycopg2.connect(DSN)
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Schema ──
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS factures (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id),
    fournisseur TEXT NOT NULL,
    montant NUMERIC(12,2) NOT NULL DEFAULT 0,
    num_facture TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    date_facture DATE DEFAULT CURRENT_DATE,
    echeance_le DATE,
    is_paid INTEGER DEFAULT 0,
    paid_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS reminders (
    id SERIAL PRIMARY KEY,
    chat_id TEXT NOT NULL,
    message TEXT NOT NULL,
    remind_at TIMESTAMPTZ NOT NULL,
    sent INTEGER DEFAULT 0,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    chat_id TEXT NOT NULL,
    direction TEXT NOT NULL,
    message_type TEXT DEFAULT 'text',
    content TEXT NOT NULL,
    intent TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_conv_chat ON conversations(chat_id, created_at DESC);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def init_db():
    """Create all tables if they don't exist."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
            # Seed default companies
            for name in ("ZIZPHYTOSERVICE", "HB ADRAR"):
                cur.execute(
                    "INSERT INTO companies (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                    (name,),
                )


def get_company_id(name: str) -> Optional[int]:
    with get_cursor() as cur:
        cur.execute("SELECT id FROM companies WHERE name = %s", (name,))
        row = cur.fetchone()
        return row["id"] if row else None


def all_companies() -> List[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute("SELECT id, name FROM companies ORDER BY name")
        return [dict(r) for r in cur.fetchall()]


# ── Factures ──
def add_facture(
    fournisseur: str,
    montant: float,
    date_facture: str = "",
    echeance_le: str = "",
    notes: str = "",
    num_facture: str = "",
    company: str = "ZIZPHYTOSERVICE",
) -> int:
    comp_id = get_company_id(company) or 1
    df = date.fromisoformat(date_facture) if date_facture else date.today()
    ech = date.fromisoformat(echeance_le) if echeance_le else None
    with get_cursor() as cur:
        cur.execute(
            """INSERT INTO factures (company_id, fournisseur, montant, date_facture, echeance_le, notes, num_facture)
               VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (comp_id, fournisseur, montant, df, ech, notes, num_facture),
        )
        return cur.fetchone()["id"]


def update_facture(invoice_id: int, **updates) -> bool:
    """Update invoice fields. Pass only changed keys as kwargs."""
    if not updates:
        return False
    allowed = {"fournisseur", "montant", "num_facture", "notes", "is_paid"}
    fields = {k: v for k, v in updates.items() if k in allowed}
    if not fields:
        return False
    set_clause = ", ".join(f"{k} = %s" for k in fields)
    vals = list(fields.values()) + [invoice_id]
    with get_cursor() as cur:
        cur.execute(
            f"UPDATE factures SET {set_clause}, updated_at = NOW() WHERE id = %s",
            vals,
        )
        return cur.rowcount > 0


def delete_facture(invoice_id: int) -> bool:
    with get_cursor() as cur:
        cur.execute("DELETE FROM factures WHERE id = %s", (invoice_id,))
        return cur.rowcount > 0


def get_facture(invoice_id: int) -> Optional[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            """SELECT f.*, c.name AS company
               FROM factures f JOIN companies c ON c.id = f.company_id
               WHERE f.id = %s""",
            (invoice_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def list_factures(company: str = "", limit: int = 50) -> List[Dict[str, Any]]:
    with get_cursor() as cur:
        if company:
            cur.execute(
                """SELECT f.*, c.name AS company
                   FROM factures f JOIN companies c ON c.id = f.company_id
                   WHERE c.name = %s ORDER BY f.date_facture DESC LIMIT %s""",
                (company, limit),
            )
        else:
            cur.execute(
                """SELECT f.*, c.name AS company
                   FROM factures f JOIN companies c ON c.id = f.company_id
                   ORDER BY f.date_facture DESC LIMIT %s""",
                (limit,),
            )
        return [dict(r) for r in cur.fetchall()]


def search_factures(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            """SELECT f.*, c.name AS company
               FROM factures f JOIN companies c ON c.id = f.company_id
               WHERE LOWER(f.fournisseur) LIKE %s
                  OR LOWER(f.notes) LIKE %s
                  OR LOWER(f.num_facture) LIKE %s
               ORDER BY f.date_facture DESC LIMIT %s""",
            (f"%{query}%", f"%{query}%", f"%{query}%", limit),
        )
        return [dict(r) for r in cur.fetchall()]


def stats_factures(company: str = "") -> Dict[str, Any]:
    with get_cursor() as cur:
        if company:
            cur.execute(
                """SELECT COUNT(*) AS total, COALESCE(SUM(montant),0) AS total_amount
                   FROM factures f JOIN companies c ON c.id = f.company_id WHERE c.name = %s""",
                (company,),
            )
            t = cur.fetchone()
            cur.execute(
                """SELECT COUNT(*) AS cnt, COALESCE(SUM(montant),0) AS amt
                   FROM factures f JOIN companies c ON c.id = f.company_id
                   WHERE c.name = %s AND f.is_paid = 0""",
                (company,),
            )
            u = cur.fetchone()
        else:
            cur.execute("SELECT COUNT(*) AS total, COALESCE(SUM(montant),0) AS total_amount FROM factures")
            t = cur.fetchone()
            cur.execute("SELECT COUNT(*) AS cnt, COALESCE(SUM(montant),0) AS amt FROM factures WHERE is_paid = 0")
            u = cur.fetchone()
    return {
        "total": t["total"],
        "total_amount": float(t["total_amount"]),
        "unpaid": u["cnt"],
        "unpaid_amount": float(u["amt"]),
        "paid": t["total"] - u["cnt"],
        "paid_amount": float(t["total_amount"]) - float(u["amt"]),
    }


# ── Reminders ──
def add_reminder(chat_id: str, message: str, remind_at: str) -> int:
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO reminders (chat_id, message, remind_at) VALUES (%s, %s, %s) RETURNING id",
            (chat_id, message, remind_at),
        )
        return cur.fetchone()["id"]


def cancel_reminder(reminder_id: int, chat_id: str = "") -> bool:
    with get_cursor() as cur:
        if chat_id:
            cur.execute(
                "UPDATE reminders SET sent = 1 WHERE id = %s AND chat_id = %s AND sent = 0",
                (reminder_id, chat_id),
            )
        else:
            cur.execute(
                "UPDATE reminders SET sent = 1 WHERE id = %s AND sent = 0",
                (reminder_id,),
            )
        return cur.rowcount > 0


def list_reminders(chat_id: str = "", limit: int = 10) -> List[Dict[str, Any]]:
    with get_cursor() as cur:
        if chat_id:
            cur.execute(
                "SELECT * FROM reminders WHERE chat_id = %s AND sent = 0 ORDER BY remind_at ASC LIMIT %s",
                (chat_id, limit),
            )
        else:
            cur.execute(
                "SELECT * FROM reminders WHERE sent = 0 ORDER BY remind_at ASC LIMIT %s",
                (limit,),
            )
        return [dict(r) for r in cur.fetchall()]


def due_reminders() -> List[Dict[str, Any]]:
    """Return all unsent reminders where remind_at <= NOW()."""
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM reminders WHERE sent = 0 AND remind_at <= NOW() ORDER BY remind_at ASC"
        )
        return [dict(r) for r in cur.fetchall()]


def mark_reminder_sent(reminder_id: int) -> bool:
    with get_cursor() as cur:
        cur.execute(
            "UPDATE reminders SET sent = 1, sent_at = NOW() WHERE id = %s",
            (reminder_id,),
        )
        return cur.rowcount > 0


# ── Conversations ──
def log_conversation(chat_id: str, direction: str, content: str, msg_type: str = "text", intent: str = ""):
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO conversations (chat_id, direction, message_type, content, intent) VALUES (%s, %s, %s, %s, %s)",
            (chat_id, direction, msg_type, content[:500], intent[:50] if intent else None),
        )


def recent_conversations(chat_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM conversations WHERE chat_id = %s ORDER BY created_at DESC LIMIT %s",
            (chat_id, limit),
        )
        return [dict(r) for r in cur.fetchall()]


# ── Settings ──
def get_setting(key: str, default: str = "") -> str:
    with get_cursor() as cur:
        cur.execute("SELECT value FROM settings WHERE key = %s", (key,))
        row = cur.fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
            (key, value),
        )
