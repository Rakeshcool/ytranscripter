# YouTubeGPT Local

A local-first YouTube transcript and export app with a React + TypeScript UI and FastAPI backend.

## Features
- Paste YouTube watch, youtu.be, Shorts, embed, or bare video ID
- Fetch existing caption tracks (including auto-generated captions when available)
- Language selection
- Readable paragraphs, timestamped lines, plain text, AI-ready Markdown, SRT, and VTT
- Copy current format and download transcript files
- Timestamp links open the video at the matching time
- Optional llama.cpp health check at `http://127.0.0.1:3000/v1/models`
- No transcript persistence by default

> This fetches existing caption tracks. It does not transcribe audio when captions are absent. YouTube may block requests or restrict captions for some videos.

## Requirements
- Windows 11
- Python 3.11+
- Node.js 20+
- Internet access for YouTube caption retrieval
- Optional: llama.cpp server listening on `127.0.0.1:3000`

## Start on Windows

Open PowerShell in this project folder.

### 1. Backend
```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

If PowerShell blocks activation:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Backend docs: http://127.0.0.1:8000/docs

### 2. Frontend (second PowerShell window)
```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```
Open http://127.0.0.1:5173

## llama.cpp
The app does not need an LLM for extraction or export. To verify the configured local OpenAI-compatible endpoint:
```powershell
curl.exe http://127.0.0.1:8000/api/llm/health
```
The backend checks `LLAMA_BASE_URL` (default `http://127.0.0.1:3000/v1`) and `/models`. If your server uses another port, update `backend/.env`.

## Troubleshooting
- `NoTranscriptFound` / no captions: the video may have no caption track.
- `TranscriptsDisabled`: captions are disabled for that video.
- `RequestBlocked` / 429: YouTube may be rate-limiting or blocking the current network/IP. Wait and retry; don't send repeated rapid requests.
- Private, members-only, or age-restricted videos may not be accessible without a supported signed-in session.
- Auto-generated captions can contain recognition mistakes; verify important quotations against the video.
- A bare video ID must be exactly 11 characters.
