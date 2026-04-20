"""
transcriber.py — Whisper-based audio transcription for the voice_module.
Uses OpenAI Whisper API (whisper-1). Reads OPENAI_API_KEY from environment.
"""

import io
import logging
import os

from openai import OpenAI

logger = logging.getLogger(__name__)


def _client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set in environment")
    return OpenAI(api_key=api_key)


async def transcribe_audio(audio_bytes: bytes, filename: str = "recording.webm") -> str:
    """
    Transcribe raw audio bytes using OpenAI Whisper (whisper-1).

    Args:
        audio_bytes: Raw audio data from the uploaded file.
        filename:    Original filename — used to hint the file format to Whisper.

    Returns:
        Clean, stripped transcription string.

    Raises:
        RuntimeError: On API failure or empty key.
    """
    if not audio_bytes:
        raise ValueError("audio_bytes must not be empty")

    client = _client()
    file_obj = io.BytesIO(audio_bytes)
    file_obj.name = filename  # Whisper uses this to detect codec

    logger.info(
        "[voice_module] Transcribing %.1f KB via Whisper (file=%s)...",
        len(audio_bytes) / 1024,
        filename,
    )

    try:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=file_obj,
        )
    except Exception as exc:
        logger.exception("[voice_module] Whisper API error")
        raise RuntimeError(f"Whisper transcription failed: {exc}") from exc

    text = (response.text or "").strip()
    logger.info("[voice_module] Transcription done — %d chars", len(text))
    return text
