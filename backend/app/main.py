from __future__ import annotations

import re
from typing import Literal
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    CouldNotRetrieveTranscript,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)


class Settings(BaseSettings):
    llama_base_url: str = "http://127.0.0.1:3000/v1"
    frontend_origin: str = "http://127.0.0.1:5173"
    request_timeout_seconds: float = 30

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
app = FastAPI(title="YouTubeGPT Local API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class TranscriptRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    language: str = Field(default="en", min_length=2, max_length=16)


def parse_video_id(value: str) -> str:
    value = value.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
        return value
    parsed = urlparse(value if "://" in value else f"https://{value}")
    host = (parsed.hostname or "").lower()
    video_id = None
    if host in {"youtu.be", "www.youtu.be"}:
        video_id = parsed.path.strip("/").split("/")[0]
    elif host.endswith("youtube.com") or host.endswith("youtube-nocookie.com"):
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [None])[0]
        else:
            match = re.match(r"^/(?:shorts|embed|live|v)/([A-Za-z0-9_-]{11})", parsed.path)
            if match:
                video_id = match.group(1)
    if not video_id or not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        raise ValueError("Enter a valid YouTube URL or 11-character video ID.")
    return video_id


def seconds_to_time(seconds: float, decimal: str = ".") -> str:
    total_ms = max(0, round(seconds * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02}{decimal}{millis:03}"


def build_paragraphs(segments: list[dict], target_chars: int = 950) -> list[dict]:
    paragraphs = []
    current_text = []
    start = None
    length = 0
    last_end = None

    def flush():
        nonlocal current_text, start, length, last_end
        text = " ".join(current_text).strip()
        if text:
            paragraphs.append({"start": start or 0.0, "text": text})
        current_text, start, length, last_end = [], None, 0, None

    for seg in segments:
        text = re.sub(r"\s+", " ", seg["text"]).strip()
        if not text:
            continue
        seg_start = float(seg["start"])
        gap = seg_start - last_end if last_end is not None else 0
        if current_text and (length >= target_chars or gap >= 2.0):
            flush()
        if start is None:
            start = seg_start
        current_text.append(text)
        length += len(text) + 1
        last_end = seg_start + float(seg.get("duration", 0))
        if length >= target_chars and re.search(r"[.!?…][\"')\]]?$", text):
            flush()
    flush()
    return paragraphs


def make_formats(data: dict) -> dict:
    segments = data["segments"]
    paragraphs = build_paragraphs(segments)
    title = data["title"]
    video_url = data["url"]
    readable = "\n\n".join(p["text"] for p in paragraphs)
    plain = " ".join(s["text"].strip() for s in segments if s["text"].strip())
    timestamped = "\n".join(
        f"[{seconds_to_time(s['start'])}] {s['text'].strip()}"
        for s in segments if s["text"].strip()
    )
    ai_md = (
        f"# {title}\n\n"
        f"- Source: {video_url}\n"
        f"- Video ID: {data['video_id']}\n"
        f"- Caption language: {data['language']}\n"
        f"- Track: {'auto-generated' if data['is_generated'] else 'manually created'}\n\n"
        + "\n\n".join(
            f"[{seconds_to_time(p['start'])}]({video_url}&t={int(p['start'])}s) {p['text']}"
            for p in paragraphs
        )
    )
    srt_blocks, vtt_blocks = [], []
    for i, seg in enumerate(segments, 1):
        text = seg["text"].strip()
        if not text:
            continue
        start = float(seg["start"])
        end = start + max(float(seg.get("duration", 0.5)), 0.1)
        srt_blocks.append(
            f"{len(srt_blocks)+1}\n{seconds_to_time(start, ',')} --> "
            f"{seconds_to_time(end, ',')}\n{text}"
        )
        vtt_blocks.append(
            f"{seconds_to_time(start)} --> {seconds_to_time(end)}\n{text}"
        )
    return {
        "readable": readable,
        "timestamps": timestamped,
        "plain": plain,
        "ai": ai_md,
        "srt": "\n\n".join(srt_blocks),
        "vtt": "WEBVTT\n\n" + "\n\n".join(vtt_blocks),
    }


@app.get("/api/health")
def health():
    return {"ok": True, "service": "youtubegpt-local"}


@app.get("/api/llm/health")
async def llm_health():
    url = settings.llama_base_url.rstrip("/") + "/models"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(url)
            response.raise_for_status()
        return {"ok": True, "endpoint": url, "models": response.json()}
    except Exception as exc:
        return {"ok": False, "endpoint": url, "error": str(exc)}


@app.post("/api/transcript")
def transcript(request: TranscriptRequest):
    try:
        video_id = parse_video_id(request.url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    canonical_url = f"https://www.youtube.com/watch?v={video_id}"
    title = f"YouTube video {video_id}"
    try:
        # oEmbed provides a display title where available; caption retrieval remains independent.
        import httpx as _httpx
        try:
            response = _httpx.get(
                "https://www.youtube.com/oembed",
                params={"url": canonical_url, "format": "json"},
                timeout=5.0,
            )
            if response.is_success:
                title = response.json().get("title") or title
        except Exception:
            pass

        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=[request.language, "en"])
        segments = [
            {"start": float(item.start), "duration": float(item.duration), "text": item.text}
            for item in fetched
        ]
        # Detect track metadata using list() when available; default conservatively.
        is_generated = False
        language = getattr(fetched, "language_code", request.language)
        try:
            transcript_list = api.list(video_id)
            for track in transcript_list:
                if track.language_code == language:
                    is_generated = bool(track.is_generated)
                    break
        except Exception:
            pass

        result = {
            "video_id": video_id,
            "url": canonical_url,
            "title": title,
            "language": language,
            "is_generated": is_generated,
            "segments": segments,
        }
        result["formats"] = make_formats(result)
        result["paragraph_count"] = len(build_paragraphs(segments))
        result["segment_count"] = len(segments)
        return result
    except TranscriptsDisabled as exc:
        raise HTTPException(status_code=404, detail="Captions are disabled for this video.") from exc
    except NoTranscriptFound as exc:
        raise HTTPException(status_code=404, detail=f"No caption track found for language '{request.language}'. Try another language.") from exc
    except VideoUnavailable as exc:
        raise HTTPException(status_code=404, detail="Video is unavailable, private, or restricted.") from exc
    except CouldNotRetrieveTranscript as exc:
        raise HTTPException(status_code=502, detail="YouTube did not return captions. It may be rate-limiting this connection; wait and retry.") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Transcript retrieval failed: {type(exc).__name__}: {exc}") from exc
