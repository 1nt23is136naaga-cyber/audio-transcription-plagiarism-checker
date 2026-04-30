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

# Ensure env vars are loaded even if storage is imported directly
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

logger = logging.getLogger(__name__)

VALID_TYPES = frozenset({"personal", "technical"})

def _get_supabase_config():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
    return url, key

def save_response(candidate_id: str, response_type: str, text: str) -> None:
    """
    Persist a transcription for a candidate to Supabase.
    """
    if response_type not in VALID_TYPES:
        raise ValueError(f"response_type must be one of {VALID_TYPES}")

    url, key = _get_supabase_config()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates" # upsert
    }

    # Fetch existing data to merge, since we need to send the whole row
    existing = get_candidate(candidate_id) or {}
    existing[response_type] = text

    payload = {
        "candidate_id": candidate_id,
        "personal": existing.get("personal"),
        "technical": existing.get("technical")
    }

    with httpx.Client() as client:
        resp = client.post(
            f"{url}/rest/v1/voice_data",
            headers=headers,
            json=payload
        )
        if not resp.is_success:
            logger.error("Supabase upsert failed: %s %s", resp.status_code, resp.text)
            raise RuntimeError(f"Database error: {resp.text}")

    logger.info(
        "[voice_module] Stored %s response for candidate=%s (%d chars)",
        response_type, candidate_id, len(text),
    )


def get_candidate(candidate_id: str) -> Optional[dict]:
    """
    Retrieve all stored responses for a candidate.
    """
    url, key = _get_supabase_config()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }

    with httpx.Client() as client:
        resp = client.get(
            f"{url}/rest/v1/voice_data",
            headers=headers,
            params={"candidate_id": f"eq.{candidate_id}"}
        )
        if not resp.is_success:
            logger.error("Supabase fetch failed: %s", resp.text)
            return None
        
        data = resp.json()
        if not data:
            return None
            
        row = data[0]
        # Remove null values to mimic the original local dict format
        return {k: v for k, v in row.items() if v is not None and k in VALID_TYPES}


def delete_candidate(candidate_id: str) -> bool:
    """
    Delete all data for a candidate.
    """
    url, key = _get_supabase_config()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }

    # Check if exists first
    existing = get_candidate(candidate_id)
    if existing is None:
        return False

    with httpx.Client() as client:
        resp = client.delete(
            f"{url}/rest/v1/voice_data",
            headers=headers,
            params={"candidate_id": f"eq.{candidate_id}"}
        )
        if not resp.is_success:
            logger.error("Supabase delete failed: %s", resp.text)
            return False

    logger.info("[voice_module] Deleted candidate=%s", candidate_id)
    return True


def list_candidates() -> list[str]:
    """Return all stored candidate IDs."""
    try:
        url, key = _get_supabase_config()
    except RuntimeError:
        return []
        
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }

    with httpx.Client() as client:
        resp = client.get(
            f"{url}/rest/v1/voice_data",
            headers=headers,
            params={"select": "candidate_id"}
        )
        if not resp.is_success:
            logger.error("Supabase list failed: %s", resp.text)
            return []
            
        data = resp.json()
        return [row["candidate_id"] for row in data]
