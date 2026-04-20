"""
storage.py — Lightweight JSON-based persistence for voice interview data.

Data file: backend/voice_data.json
Schema:
  {
    "<candidate_id>": {
      "personal":  "<transcribed text>",
      "technical": "<transcribed text>"
    },
    ...
  }
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Stored next to main.py (backend root), not inside the module folder
DATA_FILE = Path(__file__).parent.parent / "voice_data.json"

VALID_TYPES = frozenset({"personal", "technical"})


# ── Internal helpers ──────────────────────────────────────────────────────────

def _load() -> dict:
    """Load current data from disk. Returns empty dict on missing/corrupt file."""
    if not DATA_FILE.exists():
        return {}
    try:
        with DATA_FILE.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        logger.warning("[voice_module] voice_data.json unreadable — starting fresh")
        return {}


def _save(data: dict) -> None:
    """Atomically write data dict to disk."""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with DATA_FILE.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


# ── Public API ────────────────────────────────────────────────────────────────

def save_response(candidate_id: str, response_type: str, text: str) -> None:
    """
    Persist a transcription for a candidate.

    Args:
        candidate_id:   Unique identifier for the candidate session.
        response_type:  Either "personal" or "technical".
        text:           Transcribed text to store.
    """
    if response_type not in VALID_TYPES:
        raise ValueError(f"response_type must be one of {VALID_TYPES}")

    data = _load()
    if candidate_id not in data:
        data[candidate_id] = {}
    data[candidate_id][response_type] = text
    _save(data)
    logger.info(
        "[voice_module] Stored %s response for candidate=%s (%d chars)",
        response_type, candidate_id, len(text),
    )


def get_candidate(candidate_id: str) -> Optional[dict]:
    """
    Retrieve all stored responses for a candidate.

    Returns:
        Dict with keys 'personal' and/or 'technical', or None if not found.
    """
    return _load().get(candidate_id)


def delete_candidate(candidate_id: str) -> bool:
    """
    Delete all data for a candidate.

    Returns:
        True if deleted, False if candidate_id didn't exist.
    """
    data = _load()
    if candidate_id not in data:
        return False
    del data[candidate_id]
    _save(data)
    logger.info("[voice_module] Deleted candidate=%s", candidate_id)
    return True


def list_candidates() -> list[str]:
    """Return all stored candidate IDs."""
    return list(_load().keys())
