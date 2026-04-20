"""
routes.py — FastAPI router for the voice interview module.

All routes are mounted under the /voice prefix by server.py.
This file does NOT import or touch anything from the existing main.py.
"""

import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from .comparator import deep_compare
from .storage import delete_candidate, get_candidate, list_candidates, save_response
from .transcriber import transcribe_audio

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Voice Interview"])


# ── POST /voice/record/personal ───────────────────────────────────────────────

@router.post("/record/personal", summary="Record & store personal introduction")
async def record_personal(
    audio: UploadFile = File(..., description="Audio file (webm, mp3, wav, m4a…)"),
    candidate_id: str = Form(..., description="Unique candidate identifier"),
):
    """
    Accept a personal-introduction audio clip, transcribe it via Whisper,
    and persist the result keyed by candidate_id.
    """
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file received")

    try:
        text = await transcribe_audio(audio_bytes, audio.filename or "personal.webm")
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not text:
        raise HTTPException(
            status_code=422,
            detail="Whisper returned an empty transcription. Speak more clearly or try again.",
        )

    save_response(candidate_id, "personal", text)
    logger.info("[voice/record/personal] candidate=%s | %d chars stored", candidate_id, len(text))

    return {
        "candidate_id": candidate_id,
        "type": "personal",
        "transcription": text,
        "char_count": len(text),
        "word_count": len(text.split()),
    }


# ── POST /voice/record/technical ─────────────────────────────────────────────

@router.post("/record/technical", summary="Record & store technical explanation")
async def record_technical(
    audio: UploadFile = File(..., description="Audio file (webm, mp3, wav, m4a…)"),
    candidate_id: str = Form(..., description="Unique candidate identifier"),
):
    """
    Accept a technical-explanation audio clip, transcribe it via Whisper,
    and persist the result for the candidate.

    The candidate must have already submitted a personal response.
    """
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file received")

    # Guard: personal response must exist first
    existing = get_candidate(candidate_id)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Candidate '{candidate_id}' not found. "
                "Please record and save a personal response first."
            ),
        )

    try:
        text = await transcribe_audio(audio_bytes, audio.filename or "technical.webm")
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not text:
        raise HTTPException(
            status_code=422,
            detail="Whisper returned an empty transcription. Speak more clearly or try again.",
        )

    save_response(candidate_id, "technical", text)
    logger.info("[voice/record/technical] candidate=%s | %d chars stored", candidate_id, len(text))

    return {
        "candidate_id": candidate_id,
        "type": "technical",
        "transcription": text,
        "char_count": len(text),
        "word_count": len(text.split()),
    }


# ── POST /voice/compare ───────────────────────────────────────────────────────

class CompareRequest(BaseModel):
    candidate_id: str


@router.post("/compare", summary="Compare personal vs technical responses")
async def compare(req: CompareRequest):
    """
    Run a dual-mode analysis (basic similarity + GPT-4o-mini deep analysis)
    on the stored personal and technical responses for a candidate.
    """
    candidate = get_candidate(req.candidate_id)
    if candidate is None:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate '{req.candidate_id}' not found",
        )

    personal  = candidate.get("personal", "")
    technical = candidate.get("technical", "")

    if not personal:
        raise HTTPException(status_code=400, detail="Personal response not recorded yet")
    if not technical:
        raise HTTPException(status_code=400, detail="Technical response not recorded yet")

    logger.info("[voice/compare] Running analysis for candidate=%s", req.candidate_id)
    analysis = await deep_compare(personal, technical)

    return {
        "candidate_id": req.candidate_id,
        "personal_preview":  personal[:300]  + ("…" if len(personal)  > 300 else ""),
        "technical_preview": technical[:300] + ("…" if len(technical) > 300 else ""),
        "analysis": analysis,
    }


# ── GET /voice/candidates ─────────────────────────────────────────────────────

@router.get("/candidates", summary="List all stored candidate IDs")
def get_candidates():
    """Return the list of all candidate IDs that have at least one response stored."""
    return {"candidates": list_candidates()}


# ── GET /voice/candidate/{candidate_id} ───────────────────────────────────────

@router.get("/candidate/{candidate_id}", summary="Get stored data for a candidate")
def get_candidate_data(candidate_id: str):
    """Return the raw stored responses for a given candidate ID."""
    data = get_candidate(candidate_id)
    if data is None:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate '{candidate_id}' not found",
        )
    return {"candidate_id": candidate_id, "data": data}


# ── DELETE /voice/candidate/{candidate_id} ────────────────────────────────────

@router.delete("/candidate/{candidate_id}", summary="Delete a candidate's data")
def remove_candidate(candidate_id: str):
    """Permanently remove all stored responses for a candidate."""
    removed = delete_candidate(candidate_id)
    if not removed:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate '{candidate_id}' not found",
        )
    return {"deleted": True, "candidate_id": candidate_id}
