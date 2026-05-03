"""
server.py — Interview Authenticity Checker API

Runs the FastAPI app with CORS, serves interview.html, and mounts
the voice_module router (transcription + style comparison + plagiarism).

Local:
    cd backend && uvicorn server:app --reload --port 8000

Docker / Hugging Face:
    uvicorn backend.server:app --host 0.0.0.0 --port 7860
"""

import sys
import os
from pathlib import Path

# Load .env from backend directory
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
# Support both: `uvicorn server:app` (local) and `uvicorn backend.server:app` (Docker)
try:
    from voice_module.routes import router as voice_router
    from auth_routes import router as auth_router
except ModuleNotFoundError:
    from backend.voice_module.routes import router as voice_router
    from backend.auth_routes import router as auth_router

app.include_router(voice_router, prefix="/voice")
app.include_router(auth_router)

# ── Serve frontend ─────────────────────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

@app.get("/", include_in_schema=False)
def serve_landing():
    return FileResponse(FRONTEND_DIR / "landing.html")

@app.get("/interview", include_in_schema=False)
def serve_interview():
    return FileResponse(FRONTEND_DIR / "interview.html")

@app.get("/{filename:path}", include_in_schema=False)
def serve_static(filename: str):
    file_path = FRONTEND_DIR / filename
    if file_path.is_file() and file_path.suffix in {".css", ".js", ".png", ".ico", ".svg"}:
        return FileResponse(file_path)
    return FileResponse(FRONTEND_DIR / "interview.html")

@app.get("/health")
def health():
    return {"status": "ok"}
