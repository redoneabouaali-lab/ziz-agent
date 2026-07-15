"""ZIZ Agent — In-memory conversation state (per-chat)"""
from typing import Optional, Dict, Any, List

# ── Per-chat state ──
pending: Dict[str, Dict[str, Any]] = {}  # chat_id → action pending confirmation
last_invoice: Dict[str, int] = {}  # chat_id → last invoice ID
last_reminder: Dict[str, int] = {}  # chat_id → last reminder ID
company_cache: Dict[str, str] = {}  # chat_id → preferred company name

# Confirm / reject keyword sets
AFFIRM = {
    "yes", "yeah", "yep", "ok", "okay", "k", "sure", "confirm",
    "proceed", "go", "do it", "confirmer", "confirme", "confirmé",
    "oui", "valider", "d accord", "d'accord",
    "نعم", "ايوا", "اجل", "تم", "أكيد", "طيب", "هيا", "ابدأ", "ايوة",
}

REJECT = {
    "no", "nope", "nah", "cancel", "stop", "abort", "nevermind",
    "لا", "كلا", "أبدا", "توقف", "إلغاء", "لا داعي",
}


def is_affirm(text: str) -> bool:
    return text.strip().lower().rstrip("!.؟?").strip() in AFFIRM


def is_reject(text: str) -> bool:
    return text.strip().lower().rstrip("!.؟?").strip() in REJECT


def pending_action(chat_id: str) -> Optional[Dict[str, Any]]:
    return pending.get(chat_id)


def set_pending(chat_id: str, data: Dict[str, Any]):
    pending[chat_id] = data


def clear_pending(chat_id: str):
    pending.pop(chat_id, None)


def resolve_company(chat_id: str) -> str:
    """Return the preferred company for this chat, or the default."""
    from bot.config import CURRENT_COMPANY
    return company_cache.get(chat_id, CURRENT_COMPANY)
