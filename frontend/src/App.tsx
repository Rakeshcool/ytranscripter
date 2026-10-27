import { useMemo, useState } from "react";
import {
  ArrowDownToLine, Check, Clipboard, Clock3, FileText, Link2,
  LoaderCircle, Play, Sparkles, Subtitles, Youtube
} from "lucide-react";

const API = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
type FormatKey = "readable" | "timestamps" | "plain" | "ai" | "srt" | "vtt";
type Transcript = {
  video_id: string; url: string; title: string; language: string;
  is_generated: boolean; segment_count: number; paragraph_count: number;
  formats: Record<FormatKey, string>;
};
const formats: { key: FormatKey; label: string; ext: string }[] = [
  { key: "readable", label: "Readable", ext: "txt" },
  { key: "timestamps", label: "Timestamps", ext: "txt" },
  { key: "plain", label: "Plain text", ext: "txt" },
  { key: "ai", label: "For AI", ext: "md" },
  { key: "srt", label: "SRT", ext: "srt" },
  { key: "vtt", label: "VTT", ext: "vtt" }
];

export default function App() {
  const [url, setUrl] = useState("");
  const [language, setLanguage] = useState("en");
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [active, setActive] = useState<FormatKey>("readable");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  const currentFormat = useMemo(() => formats.find(f => f.key === active)!, [active]);

  async function getTranscript(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true); setError(""); setTranscript(null);
    try {
      const response = await fetch(`${API}/api/transcript`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, language })
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "Could not retrieve transcript.");
      setTranscript(body);
      setActive("readable");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error.");
    } finally {
      setLoading(false);
    }
  }

  async function copyText() {
    if (!transcript) return;
    await navigator.clipboard.writeText(transcript.formats[active]);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1400);
  }

  function downloadText() {
    if (!transcript) return;
    const blob = new Blob([transcript.formats[active]], {
      type: active === "vtt" ? "text/vtt;charset=utf-8" :
        active === "ai" ? "text/markdown;charset=utf-8" : "text/plain;charset=utf-8"
    });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    const safeTitle = transcript.title.replace(/[<>:"/\\|?*\x00-\x1F]/g, "").trim().slice(0, 100) || transcript.video_id;
    a.download = `${safeTitle}.${currentFormat.ext}`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#"><span className="brand-icon"><Youtube size={19}/></span><span>YouTubeGPT <b>Local</b></span></a>
        <div className="local-pill"><span className="status-dot"/><span>Runs on your machine</span></div>
      </header>

      <section className="hero">
        <div className="eyebrow"><Sparkles size={14}/> TRANSCRIPT WORKSPACE</div>
        <h1>Turn any video into <span>useful text.</span></h1>
        <p className="hero-copy">Clean transcripts, precise timestamps, and subtitle exports.<br className="desktop-break"/> No account. No clutter. Just the words you need.</p>

        <form className="url-form" onSubmit={getTranscript}>
          <div className="url-input-wrap"><Link2 size={19}/><input value={url} onChange={e => setUrl(e.target.value)} placeholder="Paste a YouTube link or video ID…" aria-label="YouTube URL" required /></div>
          <button className="primary-button" disabled={loading}>{loading ? <LoaderCircle className="spin" size={17}/> : <Play size={16} fill="currentColor"/>}{loading ? "Fetching…" : "Get transcript"}</button>
        </form>
        <div className="form-options">
          <span>Supports youtube.com, youtu.be, Shorts and embed links</span>
          <label>Caption language <select value={language} onChange={e => setLanguage(e.target.value)}><option value="en">English (en)</option><option value="hi">Hindi (hi)</option><option value="es">Spanish (es)</option><option value="ja">Japanese (ja)</option><option value="fr">French (fr)</option><option value="de">German (de)</option><option value="pt">Portuguese (pt)</option></select></label>
        </div>
        {error && <div className="error-box"><b>Couldn’t fetch transcript</b><span>{error}</span><small>Only existing captions can be extracted. Some videos may be restricted or temporarily blocked by YouTube.</small></div>}
      </section>

      {!transcript && !loading && (
        <section className="feature-grid">
          <div className="feature-card"><div className="feature-icon"><FileText size={18}/></div><h3>Readable by default</h3><p>Caption fragments are reassembled into paragraphs for easier reading.</p></div>
          <div className="feature-card"><div className="feature-icon"><Clock3 size={18}/></div><h3>Jump to the moment</h3><p>Keep timestamps with the transcript so important moments are easy to revisit.</p></div>
          <div className="feature-card"><div className="feature-icon"><Subtitles size={18}/></div><h3>Export your way</h3><p>Download TXT, Markdown, SRT, or VTT files in a click.</p></div>
        </section>
      )}

      {loading && <div className="loading-card"><LoaderCircle className="spin" size={22}/><span>Looking for available caption tracks…</span></div>}

      {transcript && (
        <section className="results">
          <div className="video-summary">
            <div className="video-mark"><Youtube size={24}/></div>
            <div className="video-info"><h2>{transcript.title}</h2><a href={transcript.url} target="_blank" rel="noreferrer">{transcript.url}</a><div className="meta-row"><span>{transcript.segment_count.toLocaleString()} caption segments</span><span>{transcript.paragraph_count} paragraphs</span><span>{transcript.language}</span><span className="track-badge">{transcript.is_generated ? "Auto-generated captions" : "Caption track"}</span></div></div>
            <a className="open-video" href={transcript.url} target="_blank" rel="noreferrer"><Play size={14}/> Open video</a>
          </div>
          <div className="transcript-panel">
            <div className="panel-heading"><div><h2>Transcript</h2><p>Choose a format, then copy or download.</p></div><div className="actions"><button className="secondary-button" onClick={copyText}>{copied ? <Check size={16}/> : <Clipboard size={16}/>} {copied ? "Copied" : "Copy"}</button><button className="primary-button compact" onClick={downloadText}><ArrowDownToLine size={16}/> Download .{currentFormat.ext}</button></div></div>
            <div className="format-tabs" role="tablist">{formats.map(f => <button key={f.key} role="tab" aria-selected={active === f.key} className={active === f.key ? "format-tab active" : "format-tab"} onClick={() => setActive(f.key)}>{f.label}</button>)}</div>
            <pre className="transcript-text">{transcript.formats[active]}</pre>
            <div className="panel-footer"><span>Source captions may contain recognition errors.</span><span>Transcript is processed in memory, not saved by this app.</span></div>
          </div>
        </section>
      )}

      <footer><span>YT Local <span className="footer-sep">/</span> Private by design</span><span>Caption availability depends on YouTube</span></footer>
    </main>
  );
}
