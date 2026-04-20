import os
import io
import asyncio
import logging
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
import httpx

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Transcribe & Plagiarism API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Serve frontend ───────────────────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

@app.get("/app", include_in_schema=False)
def serve_frontend():
    return FileResponse(FRONTEND_DIR / "index.html")

# ─── OpenAI client ────────────────────────────────────────────────────────────
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ─── PlagiarismCheck.org credentials ─────────────────────────────────────────
PLAGIARISM_API_TOKEN = os.getenv("PLAGIARISM_API_TOKEN")
PLAGIARISM_BASE = "https://plagiarismcheck.org/api/v1"


# ─────────────────────────────────────────────────────────────────────────────
# PlagiarismCheck.org helpers
# ─────────────────────────────────────────────────────────────────────────────

async def plag_submit(text: str) -> int:
    """Submit text for plagiarism check; returns the text ID."""
    url = f"{PLAGIARISM_BASE}/text"
    headers = {"X-API-TOKEN": PLAGIARISM_API_TOKEN}
    data = {"language": "en", "text": text}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, headers=headers, data=data)
    if not resp.is_success:
        logger.error("PlagiarismCheck submit failed: %s %s", resp.status_code, resp.text)
        raise HTTPException(status_code=502, detail=f"PlagiarismCheck submit error: {resp.text}")
    body = resp.json()
    if not body.get("success"):
        raise HTTPException(status_code=502, detail=f"PlagiarismCheck submit rejected: {body}")
    text_id = body["data"]["text"]["id"]
    logger.info("PlagiarismCheck submitted — text_id=%s", text_id)
    return text_id


async def plag_poll(text_id: int, max_wait: int = 120) -> None:
    """Poll until state == 5 (STATE_CHECKED) or timeout."""
    url = f"{PLAGIARISM_BASE}/text/{text_id}"
    headers = {"X-API-TOKEN": PLAGIARISM_API_TOKEN}
    interval = 5
    elapsed = 0
    async with httpx.AsyncClient(timeout=30) as client:
        while elapsed < max_wait:
            await asyncio.sleep(interval)
            elapsed += interval
            resp = await client.get(url, headers=headers)
            if not resp.is_success:
                logger.error("PlagiarismCheck status error: %s %s", resp.status_code, resp.text)
                raise HTTPException(status_code=502, detail=f"PlagiarismCheck status error: {resp.text}")
            body = resp.json()
            state = body.get("data", {}).get("state", 0)
            logger.info("PlagiarismCheck text_id=%s state=%s (%ss elapsed)", text_id, state, elapsed)
            if state == 5:
                return
    raise HTTPException(status_code=504, detail="PlagiarismCheck scan timed out. Try again later.")


async def plag_report(text_id: int) -> dict:
    """Fetch the detailed report for a checked text."""
    url = f"{PLAGIARISM_BASE}/text/report/{text_id}"
    headers = {"X-API-TOKEN": PLAGIARISM_API_TOKEN}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers)
    if not resp.is_success:
        logger.error("PlagiarismCheck report error: %s %s", resp.status_code, resp.text)
        raise HTTPException(status_code=502, detail=f"PlagiarismCheck report error: {resp.text}")
    body = resp.json()
    if not body.get("success", True):
        raise HTTPException(status_code=502, detail=f"PlagiarismCheck report rejected: {body}")
    return body.get("data", {})


def parse_plag_report(raw: dict) -> dict:
    """Normalise the PlagiarismCheck report into {score, sources}."""
    report_data = raw.get("report_data", {})
    matched_percent = float(report_data.get("matched_percent", 0) or 0)

    sources = []
    for src in report_data.get("sources", []):
        url = src.get("source", "")
        link_name = src.get("link", {}).get("name", "") or url
        pct = float(src.get("plagiarism_percent", 0) or 0)
        sources.append({
            "url": url,
            "title": link_name,
            "similarity": round(pct, 2),
        })

    sources.sort(key=lambda x: x["similarity"], reverse=True)
    return {"score": round(matched_percent, 2), "sources": sources[:10]}


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "ok", "message": "Transcribe & Plagiarism API is running"}


@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    """Accept an audio file and return the transcribed text via OpenAI Whisper."""
    if not openai_client.api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not set")

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file received")

    file_obj = io.BytesIO(audio_bytes)
    file_obj.name = audio.filename or "recording.webm"

    logger.info("Transcribing %d bytes of audio…", len(audio_bytes))
    try:
        response = openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=file_obj,
        )
    except Exception as exc:
        logger.exception("OpenAI transcription error")
        raise HTTPException(status_code=502, detail=f"OpenAI error: {str(exc)}")

    return {"text": response.text}


class PlagiarismRequest(BaseModel):
    text: str


@app.post("/plagiarism")
async def check_plagiarism(req: PlagiarismRequest):
    """Accept text, run a PlagiarismCheck.org scan, and return similarity score + sources."""
    if not PLAGIARISM_API_TOKEN:
        raise HTTPException(status_code=500, detail="PLAGIARISM_API_TOKEN is not set")

    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text is empty")

    if len(text) < 80:
        raise HTTPException(
            status_code=400,
            detail="Text must be at least 80 characters for plagiarism checking."
        )

    logger.info("Starting PlagiarismCheck scan for %d chars…", len(text))

    text_id = await plag_submit(text)
    await plag_poll(text_id)
    raw = await plag_report(text_id)
    result = parse_plag_report(raw)

    logger.info("Scan complete — score=%.1f%%", result["score"])
    return result
