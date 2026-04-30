---
title: Interview Authenticity Detector
emoji: 🎤
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
---

# 🎤 AI Interview Authenticity Detector

> Detect AI-assisted and plagiarised interview responses using real-time voice transcription, communication style analysis, and web plagiarism scanning.

---

## 📌 Problem Statement

In modern technical interviews — especially remote ones — candidates increasingly rely on AI tools (ChatGPT, Copilot, etc.) or pre-written scripts to answer questions. This makes it difficult for interviewers to assess a candidate's **genuine communication ability** and **authentic knowledge**.

Traditional plagiarism checkers only compare against static databases. They miss the subtle but telling pattern of a candidate who speaks casually in personal introductions but suddenly switches to polished, complex technical language — a strong signal of AI-generated content.

---

## 💡 Solution Overview

This system uses a **two-signal detection approach**:

| Signal | Method |
|--------|--------|
| **Style Shift Detection** | Compares vocabulary level, sentence complexity, grammar, formality, and fluency between the personal and technical rounds |
| **Plagiarism Scan** | Passes the technical response through the PlagiarismCheck.org API to find web source matches |

Both signals are combined into a **Final Verdict**:

| Verdict | Condition |
|---------|-----------|
| ✅ Genuine | Low style shift + Low plagiarism |
| ⚠️ Slight Concern | Moderate shift or minor plagiarism |
| 🔍 Suspicious | High style shift OR significant plagiarism |
| 🚨 Highly Suspicious | Very high style shift + high plagiarism |

---

## ✨ Key Features

- 🎙️ **Browser-based audio recording** — Record personal and technical responses directly in the browser
- 📝 **Editable transcription** — Review and correct transcribed text before running analysis
- 🧠 **Style shift detection** — Analyses 6 linguistic dimensions (vocabulary, formality, grammar, sentence length, lexical diversity, filler words)
- 📊 **Smart scoring rules**:
  - Multi-signal enforcement: 3+ strong signals → minimum shift score of 50
  - Simple→complex transition penalty: +20 to shift score
  - 4-tier verdict thresholds (< 20 / 20–40 / 40–60 / > 60)
- 🔍 **Web plagiarism scan** — Technical response checked against web sources via PlagiarismCheck.org API
- ⚡ **Non-blocking UX** — Style analysis appears in < 2 seconds; plagiarism loads in the background
- 🛡️ **Graceful error handling** — Friendly messages for API rate limits, timeouts, and missing keys

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Vanilla HTML / CSS / JavaScript (no framework) |
| **Backend** | Python 3.11+ · FastAPI · Uvicorn |
| **Transcription** | Deepgram Nova-2 (`deepgram-sdk==3.2.7`) |
| **Style Analysis** | Custom heuristic engine (`style_comparator.py`) |
| **Plagiarism** | PlagiarismCheck.org REST API |
| **Storage** | JSON file store (session-scoped) |

---

## 📁 Project Structure

```
Interview-new/
├── frontend/
│   ├── interview.html      # Main UI — recording, transcription, results
│   └── index.html          # Landing page
│
├── backend/
│   ├── server.py           # Entry point — mounts all routes
│   ├── main.py             # Base FastAPI app + legacy routes
│   ├── requirements.txt    # Python dependencies
│   ├── .env.example        # Environment variable template
│   │
│   └── voice_module/       # Core analysis module
│       ├── routes.py           # API endpoints (/voice/*)
│       ├── style_comparator.py # Style shift detection engine
│       ├── plagiarism_client.py# PlagiarismCheck.org client
│       ├── transcriber.py      # Deepgram transcription
│       ├── storage.py          # JSON session storage
│       └── __init__.py
```

---

## 🚀 Setup & Running Locally

### 1. Clone the repository

```bash
git clone https://github.com/your-username/ai-interview-authenticity-detector.git
cd ai-interview-authenticity-detector
```

### 2. Create a virtual environment

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure API keys

```bash
copy .env.example .env   # Windows
# OR
cp .env.example .env     # macOS/Linux
```

Open `backend/.env` and fill in your keys:

```env
DEEPGRAM_API_KEY=your_deepgram_key_here
OPENAI_API_KEY=your_openai_key_here         # optional
PLAGIARISM_API_TOKEN=your_plagiarism_token_here
```

| Key | Where to get it |
|-----|----------------|
| `DEEPGRAM_API_KEY` | [console.deepgram.com](https://console.deepgram.com/) |
| `OPENAI_API_KEY` | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| `PLAGIARISM_API_TOKEN` | [plagiarismcheck.org/api](https://plagiarismcheck.org/api/) |

### 5. Run the server

```bash
cd backend
python -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

### 6. Open the app

Navigate to **[http://localhost:8000/interview](http://localhost:8000/interview)** in your browser.

---

## 🎯 How to Use

1. **Enter or generate a Candidate ID** and confirm it
2. **Record or type** your personal introduction in Round 1
3. **Confirm** the transcription (edit if needed)
4. **Record or type** your technical explanation in Round 2
5. **Confirm** and click **Run Deep Analysis**
6. View:
   - **Authenticity Score** (style-based, 0–100)
   - **Style Shift Level** (LOW / MODERATE / HIGH / VERY HIGH)
   - **Plagiarism Score** (% match against web, appears after ~30–60s)
   - **Final Verdict** combining both signals

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/voice/text-compare` | Style shift analysis on raw text |
| `POST` | `/voice/plagiarism` | Plagiarism check (technical response only) |
| `POST` | `/voice/transcribe-chunk` | Transcribe an audio blob via Deepgram |
| `GET`  | `/interview` | Serve the main UI |
| `GET`  | `/docs` | Interactive API docs (Swagger UI) |

---

## 🔬 Scoring Logic

### Style Shift Score (0–100)

Weighted average of 6 linguistic dimensions:

| Dimension | Weight | What it measures |
|-----------|--------|-----------------|
| Vocabulary level | 2.5× | Avg word length + rare-word ratio |
| Formality score | 2.0× | Vocabulary + sentence length − filler words |
| Grammar score | 1.5× | Fragment detection, capitalisation, disfluencies |
| Sentence length | 1.2× | Average words per sentence |
| Lexical diversity | 1.0× | Unique word ratio |
| Filler word ratio | 0.8× | "um", "like", "basically", etc. |

**Penalty rules:**
- **Multi-signal**: 3+ strong signals → shift score enforced ≥ 50
- **Simple→Complex**: Personal simple + technical complex → +20 points

### Verdict Thresholds

| Shift Score | Style Shift | Authenticity Cap |
|-------------|-------------|-----------------|
| < 20 | LOW | 80–100 |
| 20–40 | MODERATE | 60–80 |
| 40–60 | HIGH | 40–60 |
| > 60 | VERY HIGH | 0–40 |

---

## 🔒 Security Notes

- **Never commit `.env`** — it is in `.gitignore`
- All API keys are loaded from environment variables only
- The app runs fully locally — no data is sent to external servers except the transcription and plagiarism APIs

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

*Built for interview integrity — powered by Deepgram, FastAPI, and PlagiarismCheck.org*
