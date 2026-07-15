"""ZIZ Agent — Invoice actions (CRUD + search + stats)"""
import logging
from datetime import date
from typing import Dict, Any

from bot import database as db
from bot.memory import last_invoice

logger = logging.getLogger(__name__)


def add(chat_id: str, params: Dict[str, Any]) -> str:
    fourn = params.get("fournisseur", "")
    mont = params.get("montant", 0)
    if not fourn or not mont:
        return "⚠️ Infos manquantes (fournisseur ou montant)."
    df = params.get("date_facture", date.today().isoformat())
    company = params.get("company") or ""
    inv_id = db.add_facture(fourn, float(mont), df, company=company)
    last_invoice[chat_id] = inv_id
    logger.info(f"Invoice #{inv_id} added: {fourn} {mont} DH")
    return f"✅ *Facture #{inv_id} ajoutée !*\n🏢 {fourn}\n💰 {float(mont):,.0f} DH\n📅 {df}"


def update(chat_id: str, params: Dict[str, Any]) -> str:
    inv_id = params.get("invoice_id") or last_invoice.get(chat_id, 0)
    if not inv_id:
        return "⚠️ Aucune facture récente à modifier. Précise l'ID."
    existing = db.get_facture(inv_id)
    if not existing:
        return f"⚠️ Facture #{inv_id} introuvable."
    updates = {}
    for k in ("num_facture", "notes", "fournisseur", "montant"):
        v = params.get(k)
        if v is not None and v != "":
            updates[k] = float(v) if k == "montant" else str(v)
    if not updates:
        return "ℹ️ Aucune modification."
    ok = db.update_facture(inv_id, **updates)
    if ok:
        logger.info(f"Invoice #{inv_id} updated: {updates}")
        return f"✅ *Facture #{inv_id} mise à jour !*\n📝 Modifié: {', '.join(updates.keys())}"
    return "⚠️ Erreur lors de la mise à jour."


def delete(chat_id: str, params: Dict[str, Any]) -> str:
    inv_id = params.get("invoice_id") or last_invoice.get(chat_id, 0)
    if not inv_id:
        return "⚠️ Précise l'ID de la facture à supprimer."
    existing = db.get_facture(inv_id)
    if not existing:
        return f"⚠️ Facture #{inv_id} introuvable."
    ok = db.delete_facture(inv_id)
    if ok:
        if last_invoice.get(chat_id) == inv_id:
            last_invoice.pop(chat_id, None)
        logger.info(f"Invoice #{inv_id} deleted by {chat_id}")
        return f"🗑️ *Facture #{inv_id} supprimée !*\n🏢 {existing['fournisseur']}\n💰 {existing['montant']:,.0f} DH"
    return "⚠️ Erreur lors de la suppression."


def search(chat_id: str, params: Dict[str, Any]) -> str:
    query = params.get("query", "").strip().lower()
    if not query:
        return "⚠️ Précise ta recherche."
    rows = db.search_factures(query)
    if not rows:
        return f"📭 Aucune facture pour \"{query}\"."
    msg = f"🔍 *Résultats \"{query}\"* ({len(rows)})"
    for r in rows:
        status = "✅" if r.get("is_paid") else "🔴"
        msg += f"\n{status} #{r['id']} • {r['fournisseur']} • {r['montant']:,.0f} DH"
    return msg


def list_all(chat_id: str, params: Dict[str, Any]) -> str:
    company = params.get("company") or ""
    rows = db.list_factures(company=company)
    if not rows:
        name = company or "toutes les entreprises"
        return f"📭 Aucune facture pour {name}."
    total = sum(r["montant"] for r in rows)
    unpaid = [r for r in rows if not r.get("is_paid")]
    paid = [r for r in rows if r.get("is_paid")]
    name = company or f"{len(rows)} factures"
    msg = f"📊 *Factures {name}*\n💰 Total: {total:,.0f} DH\n📋 {len(rows)} factures"
    if unpaid:
        msg += f"\n🔴 Impayé: {len(unpaid)} ({sum(r['montant'] for r in unpaid):,.0f} DH)"
    if paid:
        msg += f"\n✅ Payé: {len(paid)} ({sum(r['montant'] for r in paid):,.0f} DH)"
    if unpaid:
        msg += "\n\n📄 *Détail impayées:*"
        for r in unpaid[:8]:
            msg += f"\n• {r['fournisseur']}: {r['montant']:,.0f} DH"
        if len(unpaid) > 8:
            msg += f"\n... et {len(unpaid)-8} autre(s)"
    return msg


def stats(chat_id: str, params: Dict[str, Any]) -> str:
    company = params.get("company") or ""
    s = db.stats_factures(company=company)
    name = company or "Général"
    msg = f"📈 *Statistiques {name}*\n💰 Total: {s['total_amount']:,.0f} DH\n📋 {s['total']} factures"
    msg += f"\n🔴 Impayé: {s['unpaid']} ({s['unpaid_amount']:,.0f} DH)"
    msg += f"\n✅ Payé: {s['paid']} ({s['paid_amount']:,.0f} DH)"
    return msg
