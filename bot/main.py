#!/usr/bin/env python3
"""ZIZ Multi-Action Agent — Entry Point
Starts:
  1. Telegram long-poll bot
  2. Flask API for n8n
  3. Logging setup
"""
import logging, sys, threading, time

from bot.database import init_db
from bot.telegram import main_loop
from bot.api import start as start_api

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("main")


def reminder_check_loop():
    """Background thread: check due reminders every 30s (only when PC/local)"""
    import requests
    from bot.config import TG_TOKEN
    from bot.database import due_reminders, mark_reminder_sent

    def send_telegram(chat_id, text):
        try:
            requests.post(
                f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                params={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
                timeout=10,
            )
        except:
            pass

    while True:
        try:
            for rem in due_reminders():
                send_telegram(rem["chat_id"], f"⏰ *Rappel ZIZ*\n\n{rem['message']}")
                mark_reminder_sent(rem["id"])
                logger.info(f"Local reminder #{rem['id']} sent")
        except Exception as e:
            logger.error(f"Reminder check error: {e}")
        time.sleep(30)


def main():
    logger.info("=" * 50)
    logger.info("ZIZ Multi-Action Agent starting...")
    logger.info("=" * 50)

    # ── Initialize database ──
    try:
        init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database init failed: {e}")
        sys.exit(1)

    # ── Start threads ──
    threads = []

    # Telegram bot
    t1 = threading.Thread(target=main_loop, daemon=True, name="tg-bot")
    t1.start()
    threads.append(t1)
    logger.info("Telegram bot thread started")

    # Local reminder checker (30s loop)
    t2 = threading.Thread(target=reminder_check_loop, daemon=True, name="reminder-check")
    t2.start()
    threads.append(t2)
    logger.info("Reminder checker started")

    # Flask API (blocking — this thread hosts it)
    logger.info("Starting Flask API (main thread)...")
    start_api()  # Blocking


if __name__ == "__main__":
    main()
