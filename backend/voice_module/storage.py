"""
storage.py — Supabase-based persistence for voice interview data.

Data is stored in the `voice_data` table on Supabase.
"""

import os
import logging
from typing import Optional
import httpx
from pathlib import Path
from dotenv import load_dotenv

# Ensure env vars are loaded
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

logger = logging.getLogger(__name__)

VALID_TYPES = frozenset({"personal", "technical"})


def _get_supabase_config():
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in environment")
    return url, key


def _headers(key: str) -> dict:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def save_response(candidate_id: str, response_type: str, text: str) -> None:
    """Persist a transcription for a candidate to Supabase (upsert)."""
    if response_type not in VALID_TYPES:
        raise ValueError(f"response_type must be one of {VALID_TYPES}")

    try:
        url, key = _get_supabase_config()
    except RuntimeError as e:
        logger.warning("Supabase not configured — skipping save: %s", e)
        return  # Graceful degradation — don't crash the route

    # Fetch existing to merge
    existing = get_candidate(candidate_id) or {}
    existing[response_type] = text

    payload = {
        "candidate_id": candidate_id,
        "personal": existing.get("personal"),
        "technical": existing.get("technical"),
    }

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(
                f"{url}/rest/v1/voice_data",
                headers={**_headers(key), "Prefer": "resolution=merge-duplicates"},
                json=payload,
            )
            if not resp.is_success:
                logger.error("Supabase upsert failed: %s %s", resp.status_code, resp.text)
                # Don't raise — let the route continue
    except Exception as exc:
        logger.error("Supabase save error: %s", exc)
        # Don't crash the route over a DB error

    logger.info(
        "[voice_module] Stored %s response for candidate=%s (%d chars)",
        response_type, candidate_id, len(text),
    )


def get_candidate(candidate_id: str) -> Optional[dict]:
    """Retrieve all stored responses for a candidate."""
    try:
        url, key = _get_supabase_config()
    except RuntimeError:
        return None

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                f"{url}/rest/v1/voice_data",
                headers=_headers(key),
                params={"candidate_id": f"eq.{candidate_id}"},
            )
            if not resp.is_success:
                logger.error("Supabase fetch failed: %s", resp.text)
                return None

            data = resp.json()
            if not data:
                return None

            row = data[0]
            return {k: v for k, v in row.items() if v is not None and k in VALID_TYPES}
    except Exception as exc:
        logger.error("Supabase get error: %s", exc)
        return None


def delete_candidate(candidate_id: str) -> bool:
    """Delete all data for a candidate."""
    try:
        url, key = _get_supabase_config()
    except RuntimeError:
        return False

    existing = get_candidate(candidate_id)
    if existing is None:
        return False

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.delete(
                f"{url}/rest/v1/voice_data",
                headers=_headers(key),
                params={"candidate_id": f"eq.{candidate_id}"},
            )
            if not resp.is_success:
                logger.error("Supabase delete failed: %s", resp.text)
                return False
    except Exception as exc:
        logger.error("Supabase delete error: %s", exc)
        return False

    logger.info("[voice_module] Deleted candidate=%s", candidate_id)
    return True


def list_candidates() -> list:
    """Return all stored candidate IDs."""
    try:
        url, key = _get_supabase_config()
    except RuntimeError:
        return []

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                f"{url}/rest/v1/voice_data",
                headers=_headers(key),
                params={"select": "candidate_id"},
            )
            if not resp.is_success:
                logger.error("Supabase list failed: %s", resp.text)
                return []

            data = resp.json()
            return [row["candidate_id"] for row in data]
    except Exception as exc:
        logger.error("Supabase list error: %s", exc)
        return []
