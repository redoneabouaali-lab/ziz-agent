"""ZIZ Agent — Reminder actions"""
import logging
from typing import Dict, Any

from bot import database as db
from bot.memory import last_reminder
from bot.config import N8N_REMINDER_URL

logger = logging.getLogger(__name__)


def add(chat_id: str, params: Dict[str, Any]) -> str:
    text = params.get("text", "").strip()
    remind_at = params.get("datetime", "").strip()
    if not text or not remind_at:
        return "⚠️ Texte ou date manquant pour le rappel."
    # Store in PostgreSQL
    rem_id = db.add_reminder(chat_id, text, remind_at)
    last_reminder[chat_id] = rem_id
    # Also forward to n8n for 24/7 delivery
    if N8N_REMINDER_URL:
        try:
            import requests
            requests.post(
                N8N_REMINDER_URL,
                json={"chat_id": chat_id, "text": text, "datetime": remind_at},
                timeout=5,
            )
        except Exception as e:
            logger.warning(f"n8n forward failed: {e}")
    logger.info(f"Reminder #{rem_id} saved for {chat_id}: {text} @ {remind_at}")
    return f"✅ *Rappel enregistré !* (24/7)\n📝 {text}\n⏰ {remind_at[:16]}"


def cancel(chat_id: str, params: Dict[str, Any]) -> str:
    rem_id = params.get("reminder_id") or last_reminder.get(chat_id, 0)
    if not rem_id:
        return "⚠️ Précise l'ID du rappel à annuler."
    ok = db.cancel_reminder(rem_id, chat_id)
    if not ok:
        return f"⚠️ Rappel #{rem_id} introuvable ou déjà envoyé."
    logger.info(f"Reminder #{rem_id} cancelled by {chat_id}")
    return f"❌ *Rappel #{rem_id} annulé !*"


def list_active(chat_id: str, params: Dict[str, Any]) -> str:
    reminders = db.list_reminders(chat_id=chat_id)
    if not reminders:
        return "📭 Aucun rappel en attente."
    msg = f"⏰ *Rappels en attente ({len(reminders)})*"
    for r in reminders:
        dt = r["remind_at"].strftime("%Y-%m-%d %H:%M") if hasattr(r["remind_at"], "strftime") else str(r["remind_at"])[:16]
        msg += f"\n  #{r['id']} • {r['message'][:40]} • ⏰ {dt}"
    return msg
