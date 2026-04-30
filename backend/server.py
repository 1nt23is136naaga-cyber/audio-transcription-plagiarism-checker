"""
server.py — Interview Authenticity Checker API

Runs the FastAPI app with CORS, serves interview.html, and mounts
the voice_module router (transcription + style comparison + plagiarism).

Run:
    uvicorn server:app --reload --port 8000
"""

from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Interview Authenticity Checker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount voice module router ──────────────────────────────────────────────────
from voice_module.routes import router as voice_router
app.include_router(voice_router, prefix="/voice")

# ── Serve frontend ─────────────────────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

@app.get("/", include_in_schema=False)
@app.get("/interview", include_in_schema=False)
def serve_interview():
    return FileResponse(FRONTEND_DIR / "interview.html")

@app.get("/health")
def health():
    return {"status": "ok"}
