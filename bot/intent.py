"""ZIZ Agent — Intent parsing via NVIDIA LLM"""
import json, re, logging
from datetime import date
from typing import Optional, Dict, Any

import requests
from bot.config import NV_API_KEY, NV_MODEL, NV_URL

logger = logging.getLogger(__name__)

# ── System prompt (the brain) ──
SYSTEM_PROMPT = """You are an AI assistant for ZIZ Échéances, an invoice management app.
Companies: ZIZPHYTOSERVICE, HB ADRAR.
Understand Arabic (Darija), French, and English.

IMPORTANT: Return ONLY valid JSON, nothing else.

ACTIONS (single or compound):

1. add_invoice → {{"action":"add_invoice","fournisseur":"supplier","montant":1234,"date_facture":"YYYY-MM-DD","company":"company name"}}
2. update_invoice → {{"action":"update_invoice","invoice_id":NUMBER,"num_facture":"...","fournisseur":"...","montant":1234,"notes":"..."}}
3. delete_invoice → {{"action":"delete_invoice","invoice_id":NUMBER}}
4. search_invoice → {{"action":"search_invoice","query":"text to search"}}
5. check_invoices → {{"action":"check_invoices","company":"company name"}}
6. get_stats → {{"action":"get_stats","company":"company name"}}
7. list_companies → {{"action":"list_companies"}}
8. set_company → {{"action":"set_company","company":"HB ADRAR or ZIZPHYTOSERVICE"}}
9. remind → {{"action":"remind","text":"reminder message","datetime":"YYYY-MM-DD HH:MM"}}
10. cancel_remind → {{"action":"cancel_remind","reminder_id":NUMBER}}
11. list_reminders → {{"action":"list_reminders"}}
12. send_whatsapp → {{"action":"send_whatsapp","text":"message","phone":"optional number"}}
13. send_email → {{"action":"send_email","text":"message body","email":"optional address"}}
14. talk → {{"action":"talk","text":"your friendly reply"}}

COMPOUND: {{"actions":[{{...}},{{...}}]}} for multiple actions in one request.

EXAMPLES:
- "زيد فاتورة الصلاح 50000" → add_invoice
- "غير المبلغ ل 75000" → update_invoice
- "احذف الفاتورة رقم 5" → delete_invoice
- "حوس على CNSS" → search_invoice
- "شوف الفواتير" → check_invoices
- "شحال عندي" → get_stats
- "بدل لشركة HB ADRAR" → set_company
- "شنو الشركات" → list_companies
- "ذكرني غداً 9 الصباح نخلص" → remind
- "الغي التذكير رقم 3" → cancel_remind
- "شوف التذكيرات" → list_reminders
- "زيد الفاتورة وذكرني" → {"actions":[{add_invoice},{remind}]}
- "ذكرني وابعث واتساب" → {"actions":[{remind},{send_whatsapp}]}
- "كيف حالك" → talk

RULES:
- If user references "numero facture" right after adding → use update_invoice
- delete_invoice / cancel_remind require an ID from the user or last context
- set_company changes company for ALL future actions
- Always extract company name from text when mentioned"""


def understand(
    text: str,
    context: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Call NVIDIA LLM to parse intent. Returns parsed JSON or None."""
    if not NV_API_KEY:
        logger.warning("NV_API_KEY not set")
        return None

    today = date.today().isoformat()
    ctx = context or {}
    ctx_lines = ""
    if ctx.get("last_invoice"):
        ctx_lines += f"\nLast invoice created: ID #{ctx['last_invoice']}"
    if ctx.get("current_company"):
        ctx_lines += f"\nCurrent company: {ctx['current_company']}"

    user_prompt = f"Today: {today}{ctx_lines}\n\nUser message: {text}\n\nReturn ONLY the JSON:"

    try:
        resp = requests.post(
            NV_URL,
            headers={
                "Authorization": f"Bearer {NV_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": NV_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.05,
                "max_tokens": 500,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            logger.error(f"NVIDIA API error {resp.status_code}: {resp.text[:200]}")
            return None

        reply = resp.json()["choices"][0]["message"]["content"]
        # Extract JSON from reply (handle markdown fences etc.)
        match = re.search(r"\{.*\}", reply, re.DOTALL)
        if not match:
            logger.warning(f"No JSON found in LLM reply: {reply[:100]}")
            return None

        parsed = json.loads(match.group())
        logger.info(
            f"Intent: {parsed.get('action', parsed.get('actions', '?'))} | {str(parsed)[:100]}"
        )
        return parsed

    except requests.Timeout:
        logger.error("NVIDIA API timeout")
        return None
    except Exception as e:
        logger.error(f"NVIDIA API error: {e}")
        return None


def correct_intent(
    original_action: str,
    original_params: Dict[str, Any],
    user_correction: str,
) -> Optional[Dict[str, Any]]:
    """Ask LLM to apply a correction to pending params."""
    if not NV_API_KEY:
        return None
    prompt = f"""The user wants to correct a pending action.
Current action: {original_action}
Current params: {json.dumps(original_params, ensure_ascii=False)}

User correction: {user_correction}

Return the UPDATED params JSON with corrections applied. Keep unchanged fields.
Return ONLY the JSON object, nothing else."""
    try:
        resp = requests.post(
            NV_URL,
            headers={
                "Authorization": f"Bearer {NV_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": NV_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.05,
                "max_tokens": 300,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            return None
        reply = resp.json()["choices"][0]["message"]["content"]
        match = re.search(r"\{.*\}", reply, re.DOTALL)
        if match:
            return json.loads(match.group())
        return None
    except Exception:
        return None
