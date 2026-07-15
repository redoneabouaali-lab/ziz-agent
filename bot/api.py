"""ZIZ Agent — HTTP API (Flask) for n8n integration"""
import logging
from datetime import date

from flask import Flask, request, jsonify
from bot import database as db
from bot.config import API_PORT

logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route("/api/health")
def api_health():
    return jsonify({"status": "ok", "version": "1.0.0"})


@app.route("/api/stats")
def api_stats():
    company = request.args.get("company", "")
    return jsonify(db.stats_factures(company=company))


@app.route("/api/invoices")
def api_invoices():
    company = request.args.get("company", "")
    limit = int(request.args.get("limit", 50))
    rows = db.list_factures(company=company, limit=limit)
    return jsonify({"invoices": rows, "total": len(rows)})


@app.route("/api/invoices/<int:inv_id>")
def api_invoice(inv_id):
    row = db.get_facture(inv_id)
    if not row:
        return jsonify({"error": "not found"}), 404
    return jsonify(row)


@app.route("/api/invoices", methods=["POST"])
def api_create_invoice():
    body = request.get_json() or {}
    inv_id = db.add_facture(
        fournisseur=body.get("fournisseur", ""),
        montant=float(body.get("montant", 0)),
        date_facture=body.get("date_facture", date.today().isoformat()),
        echeance_le=body.get("echeance_le", ""),
        notes=body.get("notes", ""),
        num_facture=body.get("num_facture", ""),
        company=body.get("company", ""),
    )
    return jsonify({"id": inv_id, "status": "created"}), 201


@app.route("/api/invoices/<int:inv_id>", methods=["PUT"])
def api_update_invoice(inv_id):
    body = request.get_json() or {}
    ok = db.update_facture(inv_id, **body)
    if ok:
        return jsonify({"status": "updated"})
    return jsonify({"error": "not found or no changes"}), 404


@app.route("/api/invoices/<int:inv_id>", methods=["DELETE"])
def api_delete_invoice(inv_id):
    ok = db.delete_facture(inv_id)
    if ok:
        return jsonify({"status": "deleted"})
    return jsonify({"error": "not found"}), 404


@app.route("/api/reminders")
def api_reminders():
    chat_id = request.args.get("chat_id", "")
    rows = db.list_reminders(chat_id=chat_id)
    return jsonify({"reminders": rows, "total": len(rows)})


@app.route("/api/reminders", methods=["POST"])
def api_create_reminder():
    body = request.get_json() or {}
    rem_id = db.add_reminder(
        chat_id=body.get("chat_id", ""),
        message=body.get("text", body.get("message", "")),
        remind_at=body.get("datetime", body.get("remind_at", "")),
    )
    return jsonify({"id": rem_id, "status": "created"}), 201


@app.route("/api/reminders/<int:rem_id>", methods=["DELETE"])
def api_cancel_reminder(rem_id):
    ok = db.cancel_reminder(rem_id)
    if ok:
        return jsonify({"status": "cancelled"})
    return jsonify({"error": "not found"}), 404


@app.route("/api/conversations/<chat_id>")
def api_conversations(chat_id):
    limit = int(request.args.get("limit", 20))
    rows = db.recent_conversations(chat_id, limit)
    return jsonify({"conversations": rows})


@app.route("/api/due-reminders")
def api_due_reminders():
    """Returns reminders that are due NOW — for n8n polling."""
    rows = db.due_reminders()
    return jsonify({"reminders": rows, "total": len(rows)})


@app.route("/api/settings", methods=["GET"])
def api_get_settings():
    key = request.args.get("key", "")
    if key:
        val = db.get_setting(key)
        return jsonify({"key": key, "value": val})
    return jsonify({"error": "key required"}), 400


@app.route("/api/settings", methods=["POST"])
def api_set_settings():
    body = request.get_json() or {}
    key = body.get("key", "")
    val = body.get("value", "")
    if key and val:
        db.set_setting(key, val)
        return jsonify({"status": "saved"})
    return jsonify({"error": "key and value required"}), 400


def start():
    """Run the Flask API server."""
    logger.info(f"API server starting on port {API_PORT}")
    app.run(host="0.0.0.0", port=API_PORT, debug=False, use_reloader=False)
