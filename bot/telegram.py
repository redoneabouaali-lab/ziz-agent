"""ZIZ Agent — Telegram long-poll loop"""
import logging, time, json
from typing import Optional, Dict, Any

import requests
from bot.config import TG_TOKEN, COMPANIES, CURRENT_COMPANY, N8N_WEBHOOK_URL
from bot import database as db
from bot.intent import understand, correct_intent
from bot.memory import (
    pending, last_invoice, last_reminder, company_cache,
    is_affirm, is_reject, set_pending, clear_pending, resolve_company,
)
from bot.actions import invoices, reminders, companies, notifications

logger = logging.getLogger(__name__)

# ── Help text ──
HELP_TEXT = """🤖 *ZIZ Agent — Aide*

📄 *Factures*
• `زيد فاتورة الصلاح 50000` — Ajouter
• `غير المبلغ ل 75000` — Modifier
• `احذف الفاتورة رقم 5` — Supprimer
• `حوس على فاتورة` — Chercher
• `شوف الفواتير` — Lister
• `شحال عندي من فاتورة` — Stats

⏰ *Rappels*
• `ذكرني غداً 9 الصباح نخلص` — Créer
• `الغي التذكير رقم 3` — Annuler
• `شوف التذكيرات` — Lister

📱 *Notifications*
• `ابعث واتساب ...` — WhatsApp
• `ابعث إيميل ...` — Email

🏛️ *Entreprises*
• `بدل لشركة HB ADRAR` — Changer
• `شنو الشركات` — Lister

💬 *Autre*
• `كيف حالك` — Discussion libre
• `هذا` / `هذي` — Aide"""


def tg_send(chat_id: str, text: str):
    """Send a Telegram message."""
    if not TG_TOKEN:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            params={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
        db.log_conversation(chat_id, "bot", text)
    except Exception as e:
        logger.error(f"tg_send error: {e}")


def _describe_action(action: str, params: Dict[str, Any]) -> str:
    """Human-readable description for confirmation prompt."""
    if action == "add_invoice":
        return f"➕ *Ajout facture:*\n🏢 {params.get('fournisseur','?')}\n💰 {params.get('montant',0):,.0f} DH"
    if action == "remind":
        return f"📝 *Rappel:* {params.get('text','?')} ⏰ {params.get('datetime','?')}"
    if action == "send_whatsapp":
        return f"📱 *WhatsApp:* \"{params.get('text','?')[:60]}\""
    if action == "send_email":
        return f"📧 *Email:* \"{params.get('text','?')[:60]}\""
    if action == "delete_invoice":
        return f"🗑️ *Supprimer facture #{params.get('invoice_id','?')}*"
    if action == "cancel_remind":
        return f"❌ *Annuler rappel #{params.get('reminder_id','?')}*"
    return f"Action: {action}"


def _needs_confirm(action: str) -> bool:
    return action in (
        "add_invoice", "delete_invoice", "cancel_remind",
        "send_whatsapp", "send_email",
    )


def _exec_action(chat_id: str, action: str, params: Dict[str, Any], text_orig: str = "") -> str:
    """Dispatch to the right action handler. Returns reply text."""
    try:
        if action == "add_invoice":
            return invoices.add(chat_id, params)
        elif action == "update_invoice":
            return invoices.update(chat_id, params)
        elif action == "delete_invoice":
            return invoices.delete(chat_id, params)
        elif action == "search_invoice":
            return invoices.search(chat_id, params)
        elif action == "check_invoices":
            return invoices.list_all(chat_id, params)
        elif action == "get_stats":
            return invoices.stats(chat_id, params)
        elif action == "list_companies":
            return companies.list_companies(chat_id, params)
        elif action == "set_company":
            return companies.set_company(chat_id, params)
        elif action == "remind":
            return reminders.add(chat_id, params)
        elif action == "cancel_remind":
            return reminders.cancel(chat_id, params)
        elif action == "list_reminders":
            return reminders.list_active(chat_id, params)
        elif action == "send_whatsapp":
            return notifications.send_whatsapp(chat_id, params, text_orig)
        elif action == "send_email":
            return notifications.send_email(chat_id, params, text_orig)
        elif action == "talk":
            return params.get("text", "👋 Bonjour!")
        elif action == "get_help":
            return HELP_TEXT
        else:
            return "🤔 Je n'ai pas compris."
    except Exception as e:
        logger.error(f"Action {action} error: {e}")
        return f"⚠️ Erreur lors de l'action {action}."


def process_message(chat_id: str, text: str):
    """Main message processing pipeline."""
    db.log_conversation(chat_id, "user", text)

    # ── Help ──
    if text.strip().lower() in ("help", "/help", "مساعدة", "aide", "شنو تقدر"):
        tg_send(chat_id, HELP_TEXT)
        return

    # ── Pending confirmation flow ──
    if chat_id in pending:
        p = pending[chat_id]
        if is_affirm(text):
            clear_pending(chat_id)
            tg_send(chat_id, "👍 *Confirmation reçue !*")
            # Compound actions
            if "actions" in p:
                for act in p["actions"]:
                    reply = _exec_action(chat_id, act.get("action", ""), act, p.get("text", ""))
                    tg_send(chat_id, reply)
            else:
                reply = _exec_action(chat_id, p["action"], p["params"], p.get("text", ""))
                tg_send(chat_id, reply)
            return
        elif is_reject(text):
            clear_pending(chat_id)
            tg_send(chat_id, "❌ *Action annulée.*")
            return
        else:
            # Try correction via LLM
            if "actions" in p:
                clear_pending(chat_id)
                tg_send(chat_id, "❌ Actions annulées. Pour modifier, refais la demande.")
                return
            corrected = correct_intent(p["action"], p["params"], text)
            if corrected and corrected != p["params"]:
                merged = p["params"].copy()
                merged.update(corrected)
                desc = _describe_action(p["action"], merged)
                set_pending(chat_id, {"action": p["action"], "params": merged, "desc": desc, "text": p.get("text", "")})
                tg_send(chat_id, f"✏️ *Corrigé !*\n{desc}\n\n✅ Confirmer / ❌ Annuler ?")
            else:
                clear_pending(chat_id)
                tg_send(chat_id, "❌ Action annulée (correction non reconnue).")
            return

    # ── Intent parsing via LLM ──
    ctx = {
        "last_invoice": last_invoice.get(chat_id, 0),
        "current_company": resolve_company(chat_id),
    }
    intent = understand(text, context=ctx)
    if not intent:
        tg_send(chat_id, "🤔 Je n'ai pas compris. Essaie /help")
        return

    # ── Compound actions ──
    actions_list = intent.get("actions", [])
    if actions_list:
        descs = []
        for act in actions_list:
            a = act.get("action", "")
            descs.append(_describe_action(a, act))
        compound_desc = "\n".join(f"  {i+1}. {d}" for i, d in enumerate(descs))
        tg_send(chat_id, f"📋 *Actions composées:*\n{compound_desc}\n\n✅ Confirmer / ❌ Annuler ?")
        set_pending(chat_id, {"actions": actions_list, "desc": compound_desc, "text": text})
        return

    # ── Single action ──
    action = intent.get("action", "unknown")
    params = intent

    # Immediate actions (no confirmation needed)
    immediate = {
        "check_invoices", "get_stats", "talk", "get_help", "unknown",
        "list_reminders", "search_invoice", "set_company", "list_companies",
        "update_invoice",
    }
    if action in immediate:
        reply = _exec_action(chat_id, action, params, text)
        tg_send(chat_id, reply)
        return

    # Remind needs datetime
    if action == "remind" and params.get("datetime"):
        desc = _describe_action(action, params)
        set_pending(chat_id, {"action": action, "params": params, "desc": desc, "text": text})
        tg_send(chat_id, f"⚠️ *Confirmation requis*\n{desc}\n\n✅ Confirmer / ❌ Annuler / ✏️ Corriger ?")
        return

    # Actions needing confirmation
    if _needs_confirm(action):
        desc = _describe_action(action, params)
        set_pending(chat_id, {"action": action, "params": params, "desc": desc, "text": text})
        tg_send(chat_id, f"⚠️ *Confirmation requis*\n{desc}\n\n✅ Confirmer / ❌ Annuler ?")
        return

    tg_send(chat_id, "🤔 Je n'ai pas compris. Essaie /help")


def main_loop(stop_event=None):
    """Telegram long-poll main loop."""
    if not TG_TOKEN:
        logger.error("TG_TOKEN not configured")
        return

    offset = 0
    logger.info("Telegram bot started (polling)")

    while not (stop_event and stop_event.is_set()):
        try:
            resp = requests.get(
                f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates",
                params={"offset": offset, "timeout": 30},
                timeout=35,
            )
            data = resp.json()
            if not data.get("ok"):
                time.sleep(5)
                continue

            for upd in data.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message") or upd.get("edited_message") or {}
                chat_id = str(msg.get("chat", {}).get("id", ""))
                if not chat_id:
                    continue

                # Voice message
                voice = msg.get("voice")
                if voice:
                    logger.info(f"Voice {voice.get('duration',0)}s from {chat_id}")
                    # Download → STT → process
                    import os
                    from bot.stt import transcribe

                    fid = voice["file_id"]
                    try:
                        file_info = requests.get(
                            f"https://api.telegram.org/bot{TG_TOKEN}/getFile?file_id={fid}",
                            timeout=10,
                        ).json()
                        fp = file_info.get("result", {}).get("file_path", "")
                        if fp:
                            audio_data = requests.get(
                                f"https://api.telegram.org/file/bot{TG_TOKEN}/{fp}",
                                timeout=30,
                            ).content
                            tmp_path = f"/tmp/voice_{fid[-12:]}.ogg"
                            with open(tmp_path, "wb") as f:
                                f.write(audio_data)
                            text = transcribe(tmp_path)
                            os.remove(tmp_path)
                            if text:
                                process_message(chat_id, text)
                            else:
                                tg_send(chat_id, "❌ Je n'ai pas compris le message vocal.")
                        else:
                            tg_send(chat_id, "❌ Impossible de télécharger le vocal.")
                    except Exception as e:
                        logger.error(f"Voice processing error: {e}")
                        tg_send(chat_id, "❌ Erreur traitement vocal.")
                    continue

                # Text message
                text = msg.get("text", "").strip()
                if text:
                    logger.info(f"Text from {chat_id}: {text[:60]}")
                    process_message(chat_id, text)

        except requests.Timeout:
            continue
        except Exception as e:
            logger.error(f"Poll loop error: {e}")
            time.sleep(5)

    logger.info("Telegram bot stopped")
