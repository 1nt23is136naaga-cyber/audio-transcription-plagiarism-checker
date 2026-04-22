"""
server.py — Extended entry point for v2 of the Audio Transcription & Plagiarism API.

This file wraps the existing FastAPI app from main.py and mounts the new voice_module
router WITHOUT modifying main.py in any way. All v1 routes remain identical.

Run:
    uvicorn server:app --reload --port 8000

The existing `uvicorn main:app` command will also still work (without voice routes).
"""

# ── Load .env FIRST — use absolute path so it works regardless of CWD ─────────
from pathlib import Path as _Path
from dotenv import load_dotenv as _load_dotenv
_load_dotenv(_Path(__file__).parent / ".env", override=True)

from pathlib import Path

from fastapi.staticfiles import StaticFiles

# ── Import existing v1 app (unmodified) ───────────────────────────────────────
from main import app  # noqa: F401  — brings in all existing routes as-is

# ── Mount new voice module router ─────────────────────────────────────────────
from voice_module.routes import router as voice_router

app.include_router(voice_router, prefix="/voice")

# ── Serve the new interview frontend page ─────────────────────────────────────
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


@app.get("/interview", include_in_schema=False)
def serve_interview():
    from fastapi.responses import FileResponse
    return FileResponse(FRONTEND_DIR / "interview.html")


@app.get("/text-test", include_in_schema=False)
def serve_text_test():
    from fastapi.responses import FileResponse
    return FileResponse(FRONTEND_DIR / "text_test.html")

