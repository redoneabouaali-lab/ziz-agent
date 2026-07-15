"""ZIZ Agent — Company management actions"""
import logging
from typing import Dict, Any

from bot import database as db
from bot.memory import company_cache
from bot.config import COMPANIES, CURRENT_COMPANY

logger = logging.getLogger(__name__)


def set_company(chat_id: str, params: Dict[str, Any]) -> str:
    comp = params.get("company", "").strip()
    if not comp:
        return _list_companies(chat_id, params)
    # Try to match
    match = None
    for c in COMPANIES:
        if comp.lower() in c.lower() or c.lower() in comp.lower():
            match = c
            break
    if not match:
        return f"⚠️ Entreprise \"{comp}\" introuvable. Disponibles: {', '.join(COMPANIES)}"
    company_cache[chat_id] = match
    logger.info(f"Company changed for {chat_id}: {match}")
    return f"✅ *Entreprise changée !*\n🏛️ {match}"


def list_companies(chat_id: str, params: Dict[str, Any]) -> str:
    return _list_companies(chat_id, params)


def _list_companies(chat_id: str, params: Dict[str, Any]) -> str:
    current = company_cache.get(chat_id, CURRENT_COMPANY)
    msg = f"🏛️ *Entreprises disponibles ({len(COMPANIES)})*\n"
    for c in COMPANIES:
        mark = "✅ " if c == current else "• "
        msg += f"{mark}{c}\n"
    msg += "\nDis: *بدل لشركة HB ADRAR* pour changer"
    return msg
