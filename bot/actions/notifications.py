"""ZIZ Agent — Multi-platform notifications (WhatsApp via OpenWA, Email via SMTP)"""
import logging, re, smtplib, ssl
from email.message import EmailMessage
from typing import Dict, Any

import requests
from bot.config import WA_URL, WA_API_KEY, WA_SESSION, WA_PHONE, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, EMAIL_TO

logger = logging.getLogger(__name__)


def send_whatsapp(chat_id: str, params: Dict[str, Any], text_orig: str = "") -> str:
    text = params.get("text", text_orig)
    if not text:
        return "⚠️ Texte manquant pour WhatsApp."
    if not WA_URL or not WA_API_KEY:
        return "❌ OpenWA non configuré. Vérifie WA_URL et WA_API_KEY."

    phones = params.get("phone", WA_PHONE)
    num_list = re.split(r"[,;\s]+", phones.strip())
    sent = 0
    for phone in num_list:
        clean = re.sub(r"[^\d]", "", phone)
        if len(clean) < 8:
            continue
        try:
            resp = requests.post(
                f"{WA_URL}/api/sessions/{WA_SESSION}/messages/send-text",
                headers={"X-API-Key": WA_API_KEY, "Content-Type": "application/json"},
                json={"chatId": f"{clean}@c.us", "text": text},
                timeout=15,
            )
            if resp.status_code in (200, 201):
                sent += 1
        except Exception as e:
            logger.error(f"WhatsApp send error: {e}")

    if sent:
        logger.info(f"WhatsApp sent to {sent} number(s)")
        return f"✅ *WhatsApp envoyé !* ({sent} destinataire(s))"
    return "❌ *Échec WhatsApp.* Vérifie la config OpenWA."


def send_email(chat_id: str, params: Dict[str, Any], text_orig: str = "") -> str:
    text = params.get("text", text_orig)
    if not text:
        return "⚠️ Texte manquant pour l'email."
    to_addr = params.get("email", EMAIL_TO)
    subject = f"📬 ZIZ Échéances — {text[:40]}"

    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS:
        return "❌ SMTP non configuré."

    try:
        msg = EmailMessage()
        msg.set_content(text)
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = to_addr
        with smtplib.SMTP(SMTP_HOST, int(SMTP_PORT), timeout=15) as s:
            s.starttls(context=ssl.create_default_context())
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        logger.info(f"Email sent to {to_addr}")
        return f"✅ *Email envoyé à {to_addr} !*"
    except Exception as e:
        logger.error(f"Email error: {e}")
        return f"❌ *Échec email.* {e}"
