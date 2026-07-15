"""ZIZ Agent — Speech-to-Text via Groq Whisper"""
import logging
from typing import Optional

import requests
from bot.config import GROQ_API_KEY

logger = logging.getLogger(__name__)

STT_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
STT_MODEL = "whisper-large-v3-turbo"


def transcribe(audio_path: str, language: str = "ar") -> Optional[str]:
    """Transcribe an audio file to text. Path must point to a .ogg file."""
    if not GROQ_API_KEY:
        logger.warning("GROQ_API_KEY not set")
        return None
    try:
        with open(audio_path, "rb") as f:
            resp = requests.post(
                STT_URL,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                files={"file": ("audio.ogg", f, "audio/ogg")},
                data={"model": STT_MODEL, "language": language, "response_format": "json"},
                timeout=60,
            )
        if resp.status_code == 200:
            text = resp.json().get("text", "")
            logger.info(f"STT: {text[:60]}")
            return text
        logger.error(f"STT error {resp.status_code}: {resp.text[:100]}")
        return None
    except Exception as e:
        logger.error(f"STT exception: {e}")
        return None
