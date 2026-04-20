# Audio Transcription & Plagiarism Checker — v1.0

A minimal full-stack web app that lets you:

- 🎙️ **Record** audio in the browser (Web Speech API — live, real-time)
- ✍️  **Transcribe** speech to text as you speak (or type/paste manually)
- 🔍 **Check plagiarism** via the [PlagiarismCheck.org](https://plagiarismcheck.org) API

---

## Folder Structure

```
Interview-new/
├── backend/
│   ├── main.py            ← FastAPI app (all endpoints)
│   ├── requirements.txt
│   └── .env.example       ← copy to .env and fill in your keys
└── frontend/
    └── index.html         ← single-file UI (served via backend or opened directly)
```

---

## Prerequisites

| Tool    | Version                                              |
|---------|------------------------------------------------------|
| Python  | 3.10+                                                |
| pip     | latest                                               |
| Browser | Chrome / Edge (Web Speech API + mic access required) |

### API Keys Required

| Service             | Where to get it                                              |
|---------------------|--------------------------------------------------------------|
| **OpenAI**          | https://platform.openai.com/api-keys                        |
| **PlagiarismCheck** | https://plagiarismcheck.org → Register → API Token           |

---

## Setup & Run

### 1 — Clone / open the project

```powershell
cd e:\AntiGravity\Interview-new
```

### 2 — Set up the backend

```powershell
cd backend

# Create & activate virtual environment
python -m venv venv
.\venv\Scripts\activate          # Windows
# source venv/bin/activate       # Linux / Mac

# Install dependencies
pip install -r requirements.txt

# Create your .env file
copy .env.example .env
```

Open `.env` and fill in your real API keys:

```env
OPENAI_API_KEY=sk-...
PLAGIARISM_API_TOKEN=your-plagiarismcheck-token
```

### 3 — Start the backend

```powershell
# inside backend/ with venv active
uvicorn main:app --reload --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### 4 — Open the app

Visit **http://localhost:8000/app** in Chrome or Edge.

> The frontend is served directly by the backend — no separate server needed.

---

## How to Use

1. Click **▶ Start Recording** — speak clearly into your microphone
2. Watch the text appear live in the transcript area as you speak
3. Click **⏹ Stop Recording** when done
4. Click **🔍 Check Plagiarism** and wait ~10–30 seconds for results
5. View your plagiarism **score** and matched **sources**

> You can also skip recording and just **type or paste** text directly into the textarea, then check it.

---

## API Endpoints

| Method | Path          | Description                                                       |
|--------|---------------|-------------------------------------------------------------------|
| `POST` | `/transcribe` | Accepts `multipart/form-data` with field `audio`. Returns `{ "text": "..." }` |
| `POST` | `/plagiarism` | Accepts `{ "text": "..." }` JSON. Returns `{ "score": 55.7, "sources": [...] }` |
| `GET`  | `/app`        | Serves the frontend HTML                                          |

### Example `/plagiarism` response

```json
{
  "score": 55.7,
  "sources": [
    {
      "url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
      "title": "Artificial intelligence - Wikipedia",
      "similarity": 38.5
    }
  ]
}
```

---

## Notes

- The plagiarism scan is **asynchronous** — the backend polls every 5 seconds (up to 2 minutes) until complete.
- Text must be **at least 80 characters** to be submitted for plagiarism checking.
- The PlagiarismCheck.org free tier uses **bonus credits**; monitor your quota on their dashboard.

---

## Troubleshooting

| Symptom                          | Fix                                                      |
|----------------------------------|----------------------------------------------------------|
| `OPENAI_API_KEY is not set`      | Fill in `.env` and restart uvicorn                       |
| `PLAGIARISM_API_TOKEN is not set`| Fill in `.env` and restart uvicorn                       |
| Text too short error             | Speak/type at least 80 characters                        |
| Mic not working                  | Allow browser mic permissions; use Chrome/Edge on localhost |
| CORS error in console            | Ensure backend is running on `localhost:8000`            |
| Scan timed out (504)             | PlagiarismCheck.org is slow — retry in a moment          |
