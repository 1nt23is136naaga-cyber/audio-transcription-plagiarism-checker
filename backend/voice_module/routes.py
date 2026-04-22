"""
routes.py — FastAPI router for the voice interview module.

All routes are mounted under the /voice prefix by server.py.
This file does NOT import or touch anything from the existing main.py.
"""

import asyncio
import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from .style_comparator import calculate_style_shift
from .plagiarism_client import check_text as plag_check, check_ai_content as ai_check
from .storage import delete_candidate, get_candidate, list_candidates, save_response
from .transcriber import transcribe_audio

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Voice Interview"])


# ── Verdict logic ─────────────────────────────────────────────────────────────

def compute_final_verdict(style: dict, plag: dict) -> str:
    """
    Combine style-shift signal and plagiarism score into one final verdict.

    Genuine          → style_shift LOW   AND plagiarism < 20 %
    Needs Review     → style_shift MEDIUM AND plagiarism < 40 %
    Suspicious       → style_shift HIGH  OR  plagiarism >= 40 %
    Highly Suspicious→ style_shift HIGH  AND plagiarism >= 40 %
    """
    shift       = style.get("style_shift", "LOW").upper()
    plag_score  = plag.get("score")          # float or None on error

    # If plagiarism API errored, treat as unknown (0 for verdict logic)
    p = float(plag_score) if plag_score is not None else 0.0

    high_shift = shift == "HIGH"
    high_plag  = p >= 40.0
    med_shift  = shift == "MEDIUM"

    if high_shift and high_plag:
        return "HIGHLY SUSPICIOUS"
    if high_shift or high_plag:
        return "SUSPICIOUS"
    if med_shift or p >= 20.0:
        return "NEEDS REVIEW"
    return "GENUINE"


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
    """
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file received")

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


class TextCompareRequest(BaseModel):
    """Direct text comparison — no audio / transcription required."""
    candidate_id: str
    personal: str
    technical: str


async def _run_full_analysis(personal: str, technical: str) -> dict:
    """
    Run style-shift analysis + plagiarism check in parallel.
    Returns the merged analysis dict ready for the API response.
    """
    # style_compare is pure Python (no I/O) — run directly
    # plag_check is async + slow (network polling) — awaited after style
    style_result, plag_result = await asyncio.gather(
        asyncio.to_thread(style_compare, personal, technical),
        plag_check(technical),
    )

    verdict = compute_final_verdict(style_result, plag_result)

    return {
        **style_result,
        "plagiarism": plag_result,
        "verdict":    verdict,
    }


@router.post(
    "/text-compare",
    summary="Compare personal vs technical responses (manual text input)",
)
async def text_compare(req: TextCompareRequest):
    personal  = req.personal.strip()
    technical = req.technical.strip()
    if not personal:
        raise HTTPException(status_code=400, detail="personal text is empty")
    if not technical:
        raise HTTPException(status_code=400, detail="technical text is empty")
    save_response(req.candidate_id, "personal",  personal)
    save_response(req.candidate_id, "technical", technical)
    logger.info("[voice/text-compare] candidate=%s | p=%d | t=%d",
                req.candidate_id, len(personal), len(technical))
    import asyncio as _aio
    analysis = await _aio.to_thread(calculate_style_shift, personal, technical)
    return {
        "candidate_id":      req.candidate_id,
        "personal_preview":  personal[:300],
        "technical_preview": technical[:300],
        "analysis":          analysis,
    }


@router.post("/compare", summary="Compare personal vs technical responses (from audio)")
async def compare(req: CompareRequest):
    """
    Run the full style-shift + plagiarism dual-signal analysis on the stored
    personal and technical responses for a candidate (recorded via audio).
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
    analysis = await _run_full_analysis(personal, technical)

    return {
        "candidate_id":      req.candidate_id,
        "personal_preview":  personal[:300]  + ("…" if len(personal)  > 300 else ""),
        "technical_preview": technical[:300] + ("…" if len(technical) > 300 else ""),
        "analysis":          analysis,
    }


# ── POST /voice/transcribe-chunk ──────────────────────────────────────────────

@router.post("/transcribe-chunk", summary="Transcribe a short audio clip via Whisper")
async def transcribe_chunk(
    audio: UploadFile = File(..., description="Audio file (webm, mp3, wav, m4a…)"),
    type: str = Form(default="personal", description="'personal' or 'technical'"),
):
    """
    Accept a short audio clip and return its Whisper transcription.
    Used by the frontend to populate text areas after browser mic recording
    or file upload - without requiring a full candidate session.
    """
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file received")

    try:
        text = await transcribe_audio(audio_bytes, audio.filename or f"{type}.webm")
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    logger.info("[voice/transcribe-chunk] type=%s | %d chars transcribed", type, len(text))
    return {
        "type":       type,
        "text":       text,
        "word_count": len(text.split()) if text else 0,
        "char_count": len(text),
    }


# ── POST /voice/plagiarism ────────────────────────────────────────────────────

class PlagCheckRequest(BaseModel):
    """Run plagiarism check on interview responses. personal is optional."""
    personal:  str = ""   # optional — leave empty to skip
    technical: str


@router.post("/plagiarism", summary="Run plagiarism & AI detection on interview responses")
async def run_plagiarism(req: PlagCheckRequest):
    """
    Submit the technical (and optionally personal) explanation to Winston AI.
    Runs BOTH Plagiarism Check and AI Content Detection in parallel.
    """
    p_text = req.personal.strip()
    t_text = req.technical.strip()

    if not t_text:
        raise HTTPException(status_code=400, detail="technical text is empty")

    logger.info(
        "[voice/plagiarism] personal=%d chars | technical=%d chars",
        len(p_text), len(t_text),
    )

    # Prepare parallel tasks
    tasks = {
        "t_plag": plag_check(t_text),
        "t_ai":   ai_check(t_text),
    }
    
    if p_text:
        tasks["p_plag"] = plag_check(p_text)
        tasks["p_ai"] =   ai_check(p_text)

    # Run all simultaneously
    keys = list(tasks.keys())
    results = await asyncio.gather(*(tasks[k] for k in keys))
    res_dict = dict(zip(keys, results))

    t_result = {
        "plagiarism": res_dict["t_plag"],
        "ai_detection": res_dict["t_ai"],
    }
    
    p_result = None
    if p_text:
        p_result = {
            "plagiarism": res_dict["p_plag"],
            "ai_detection": res_dict["p_ai"],
        }

    return {"personal": p_result, "technical": t_result}


# ── GET /voice/candidates ─────────────────────────────────────────────────────

@router.get("/candidates", summary="List all stored candidate IDs")
def get_candidates():
    return {"candidates": list_candidates()}


# ── GET /voice/candidate/{candidate_id} ───────────────────────────────────────

@router.get("/candidate/{candidate_id}", summary="Get stored data for a candidate")
def get_candidate_data(candidate_id: str):
    data = get_candidate(candidate_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found")
    return {"candidate_id": candidate_id, "data": data}


# ── DELETE /voice/candidate/{candidate_id} ────────────────────────────────────

@router.delete("/candidate/{candidate_id}", summary="Delete a candidate's data")
def remove_candidate(candidate_id: str):
    removed = delete_candidate(candidate_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found")
    return {"deleted": True, "candidate_id": candidate_id}
