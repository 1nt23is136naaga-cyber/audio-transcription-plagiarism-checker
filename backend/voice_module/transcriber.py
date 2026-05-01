"""
transcriber.py — Deepgram-based audio transcription for the voice_module.
Uses Deepgram Nova-2 model. Reads DEEPGRAM_API_KEY from environment.
Falls back gracefully with a clear error if the key is missing.
"""

import logging
import os

from deepgram import DeepgramClient, PrerecordedOptions

logger = logging.getLogger(__name__)


def _client() -> DeepgramClient:
    api_key = os.getenv("DEEPGRAM_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("DEEPGRAM_API_KEY is not set in environment")
    return DeepgramClient(api_key)


async def transcribe_audio(audio_bytes: bytes, filename: str = "recording.webm") -> str:
    """
    Transcribe raw audio bytes using Deepgram Nova-2.

    Args:
        audio_bytes: Raw audio data from the uploaded file.
        filename:    Original filename — used to detect MIME type.

    Returns:
        Clean, stripped transcription string.

    Raises:
        RuntimeError: On API failure or empty key.
        ValueError:   If audio_bytes is empty.
    """
    if not audio_bytes:
        raise ValueError("audio_bytes must not be empty")

    client = _client()

    # Detect MIME type from filename extension
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "webm"
    mime_map = {
        "webm": "audio/webm",
        "mp3":  "audio/mpeg",
        "wav":  "audio/wav",
        "m4a":  "audio/mp4",
        "ogg":  "audio/ogg",
        "flac": "audio/flac",
    }
    mimetype = mime_map.get(ext, "audio/webm")

    logger.info(
        "[voice_module] Transcribing %.1f KB via Deepgram Nova-2 (file=%s, mime=%s)...",
        len(audio_bytes) / 1024,
        filename,
        mimetype,
    )

    payload = {"buffer": audio_bytes, "mimetype": mimetype}

    options = PrerecordedOptions(
        model="nova-2",
        language="en",
        smart_format=True,
        punctuate=True,
        utterances=False,
    )

    try:
        response = client.listen.prerecorded.v("1").transcribe_file(payload, options)
    except Exception as exc:
        logger.exception("[voice_module] Deepgram API error")
        raise RuntimeError(f"Deepgram transcription failed: {exc}") from exc

    try:
        text = (
            response["results"]["channels"][0]["alternatives"][0]["transcript"] or ""
        ).strip()
    except (KeyError, IndexError, TypeError) as exc:
        logger.error("[voice_module] Unexpected Deepgram response structure: %s", response)
        raise RuntimeError(f"Could not parse Deepgram response: {exc}") from exc

    logger.info("[voice_module] Transcription done — %d chars", len(text))
    return text
