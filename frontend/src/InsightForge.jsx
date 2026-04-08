import { useState, useRef, useCallback } from "react";

const ACCEPTED = [
  "csv","xlsx","json","sql","sqlite","xml","txt","tsv","log","dat","yaml","yml","parquet","zip"
];

const API_URL = `${import.meta.env.VITE_API_URL}/analyze`;

// States: idle | loading | done | error
export default function InsightForge() {
  const [dragging, setDragging]   = useState(false);
  const [file, setFile]           = useState(null);
  const [status, setStatus]       = useState("idle");   // idle | loading | done | error
  const [downloadUrl, setDownloadUrl] = useState(null);
  const [errorMsg, setErrorMsg]   = useState("");
  const inputRef = useRef();

  const handleFile = (f) => {
    if (!f) return;
    const ext = f.name.split(".").pop().toLowerCase();
    if (ACCEPTED.includes(ext)) {
      setFile(f);
      setStatus("idle");
      setDownloadUrl(null);
      setErrorMsg("");
    }
  };

  const onDrop = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    handleFile(e.dataTransfer.files[0]);
  }, []);

  const onDragOver  = (e) => { e.preventDefault(); setDragging(true); };
  const onDragLeave = () => setDragging(false);

  const formatSize = (bytes) => {
    if (bytes < 1024)    return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1048576).toFixed(1)} MB`;
  };

  // ── Core: POST file → get PDF blob back ──────────────────────────────────
  const handleActivate = async () => {
    if (!file) return;
    setStatus("loading");
    setDownloadUrl(null);
    setErrorMsg("");

    try {
      const form = new FormData();
      form.append("file", file);

      const res = await fetch(API_URL, { method: "POST", body: form });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Unknown error" }));
        throw new Error(err.detail || `Server error ${res.status}`);
      }

      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      setDownloadUrl(url);
      setStatus("done");
    } catch (e) {
      setErrorMsg(e.message);
      setStatus("error");
    }
  };

  const handleDownload = () => {
    if (!downloadUrl) return;
    const a = document.createElement("a");
    a.href = downloadUrl;
    a.download = "InsightForge_Report.pdf";
    a.click();
  };

  const reset = () => {
    setFile(null);
    setStatus("idle");
    setDownloadUrl(null);
    setErrorMsg("");
  };

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=DM+Mono:wght@300;400;500&display=swap');

        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

        :root {
          --bg: #08090c;
          --surface: #0f1117;
          --border: rgba(255,255,255,0.07);
          --border-active: rgba(99,211,150,0.5);
          --accent: #63d396;
          --accent-dim: rgba(99,211,150,0.12);
          --accent-glow: rgba(99,211,150,0.25);
          --text: #f0f2f5;
          --muted: rgba(240,242,245,0.4);
          --danger: #ff5f6d;
          --warning: #f59e0b;
        }

        html, body { height: 100%; background: var(--bg); }

        .root {
          min-height: 100vh;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          font-family: 'DM Mono', monospace;
          background: var(--bg);
          position: relative;
          overflow: hidden;
          padding: 40px 20px;
        }

        .grid-bg {
          position: absolute; inset: 0;
          background-image:
            linear-gradient(rgba(255,255,255,0.028) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.028) 1px, transparent 1px);
          background-size: 60px 60px;
          pointer-events: none;
        }

        .blob {
          position: absolute; border-radius: 50%;
          filter: blur(90px); pointer-events: none;
          animation: blobPulse 8s ease-in-out infinite alternate;
        }
        .blob-1 {
          width: 420px; height: 420px;
          background: radial-gradient(circle, rgba(99,211,150,0.12) 0%, transparent 70%);
          top: -80px; left: -100px;
        }
        .blob-2 {
          width: 360px; height: 360px;
          background: radial-gradient(circle, rgba(99,180,211,0.09) 0%, transparent 70%);
          bottom: -60px; right: -80px; animation-delay: -4s;
        }
        @keyframes blobPulse {
          from { transform: scale(1) translateY(0); opacity: 0.7; }
          to   { transform: scale(1.1) translateY(-20px); opacity: 1; }
        }

        .card {
          position: relative; z-index: 10;
          width: 100%; max-width: 640px;
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: 20px;
          padding: 52px 48px 48px;
          display: flex; flex-direction: column; gap: 28px;
          animation: cardIn 0.7s cubic-bezier(0.22, 1, 0.36, 1) both;
        }
        @keyframes cardIn {
          from { opacity: 0; transform: translateY(28px) scale(0.98); }
          to   { opacity: 1; transform: none; }
        }

        .header { text-align: center; }
        .badge {
          display: inline-block;
          font-size: 10px; font-family: 'DM Mono', monospace;
          font-weight: 500; letter-spacing: 2.5px; text-transform: uppercase;
          color: var(--accent); background: var(--accent-dim);
          border: 1px solid rgba(99,211,150,0.2);
          border-radius: 999px; padding: 4px 12px; margin-bottom: 20px;
          animation: fadeSlide 0.6s 0.1s both;
        }
        .title {
          font-family: 'Syne', sans-serif; font-weight: 800;
          font-size: clamp(36px, 6vw, 52px);
          color: var(--text); letter-spacing: -1.5px; line-height: 1;
          animation: fadeSlide 0.6s 0.2s both;
        }
        .title span { color: var(--accent); }
        .tagline {
          margin-top: 10px; font-size: 13px;
          color: var(--muted); letter-spacing: 0.3px;
          animation: fadeSlide 0.6s 0.3s both;
        }
        @keyframes fadeSlide {
          from { opacity: 0; transform: translateY(12px); }
          to   { opacity: 1; transform: none; }
        }

        /* ── Drop zone ── */
        .dropzone {
          border: 1.5px dashed var(--border); border-radius: 14px;
          padding: 40px 24px;
          display: flex; flex-direction: column; align-items: center; gap: 14px;
          cursor: pointer; transition: all 0.25s ease; background: transparent;
          animation: fadeSlide 0.6s 0.4s both;
          position: relative; overflow: hidden;
        }
        .dropzone::after {
          content: ''; position: absolute; inset: 0;
          background: var(--accent-dim); opacity: 0;
          transition: opacity 0.25s ease; border-radius: inherit;
        }
        .dropzone:hover, .dropzone.drag-over { border-color: var(--border-active); }
        .dropzone:hover::after, .dropzone.drag-over::after { opacity: 1; }
        .dropzone.drag-over { box-shadow: 0 0 0 3px var(--accent-glow); }

        .dz-icon {
          width: 48px; height: 48px; border-radius: 12px;
          background: var(--accent-dim);
          border: 1px solid rgba(99,211,150,0.2);
          display: flex; align-items: center; justify-content: center;
          transition: transform 0.2s ease; position: relative; z-index: 1;
        }
        .dropzone:hover .dz-icon, .dropzone.drag-over .dz-icon { transform: translateY(-3px); }
        .dz-icon svg {
          width: 22px; height: 22px; stroke: var(--accent);
          fill: none; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round;
        }
        .dz-text { text-align: center; position: relative; z-index: 1; }
        .dz-primary { font-size: 14px; color: var(--text); font-weight: 500; }
        .dz-primary strong { color: var(--accent); font-weight: 500; }
        .dz-secondary { margin-top: 5px; font-size: 11px; color: var(--muted); }
        .format-chips {
          display: flex; flex-wrap: wrap; gap: 5px; justify-content: center;
          position: relative; z-index: 1; max-width: 420px;
        }
        .chip {
          font-family: 'DM Mono', monospace; font-size: 9.5px;
          font-weight: 500; letter-spacing: 1px; text-transform: uppercase;
          color: var(--muted); background: rgba(255,255,255,0.04);
          border: 1px solid var(--border); border-radius: 4px;
          padding: 3px 7px; transition: all 0.15s;
        }
        .dropzone:hover .chip {
          color: rgba(99,211,150,0.7); border-color: rgba(99,211,150,0.15);
        }

        /* ── File card ── */
        .file-card {
          border: 1px solid var(--border-active); border-radius: 14px;
          padding: 16px 20px;
          display: flex; align-items: center; gap: 14px;
          background: var(--accent-dim);
          animation: popIn 0.3s cubic-bezier(0.22, 1, 0.36, 1) both;
        }
        @keyframes popIn {
          from { opacity: 0; transform: scale(0.95); }
          to   { opacity: 1; transform: none; }
        }
        .file-ext {
          width: 40px; height: 40px; border-radius: 8px;
          background: rgba(99,211,150,0.15);
          border: 1px solid rgba(99,211,150,0.25);
          display: flex; align-items: center; justify-content: center;
          flex-shrink: 0;
          font-family: 'DM Mono', monospace; font-size: 9px;
          font-weight: 500; letter-spacing: 1px;
          color: var(--accent); text-transform: uppercase;
        }
        .file-info { flex: 1; min-width: 0; }
        .file-name {
          font-size: 13px; font-weight: 500; color: var(--text);
          white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        .file-size { font-size: 11px; color: var(--muted); margin-top: 2px; }
        .file-remove {
          background: none; border: none; cursor: pointer;
          color: var(--muted); padding: 4px; border-radius: 6px;
          display: flex; align-items: center; transition: color 0.15s; flex-shrink: 0;
        }
        .file-remove:hover { color: var(--danger); }
        .file-remove svg {
          width: 16px; height: 16px; stroke: currentColor;
          fill: none; stroke-width: 2; stroke-linecap: round;
        }

        /* ── Loading bar ── */
        .loading-box {
          border: 1px solid rgba(99,211,150,0.2); border-radius: 14px;
          padding: 20px 24px;
          background: var(--accent-dim);
          animation: popIn 0.3s both;
        }
        .loading-label {
          font-size: 12px; color: var(--accent); margin-bottom: 12px;
          display: flex; align-items: center; gap: 8px;
        }
        .spinner {
          width: 14px; height: 14px;
          border: 2px solid rgba(99,211,150,0.3);
          border-top-color: var(--accent);
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
          flex-shrink: 0;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .progress-track {
          height: 3px; border-radius: 99px;
          background: rgba(255,255,255,0.06); overflow: hidden;
        }
        .progress-bar {
          height: 100%; border-radius: 99px;
          background: var(--accent);
          animation: indeterminate 1.4s ease-in-out infinite;
          transform-origin: left;
        }
        @keyframes indeterminate {
          0%   { transform: scaleX(0) translateX(0); }
          50%  { transform: scaleX(0.6) translateX(60%); }
          100% { transform: scaleX(0) translateX(300%); }
        }

        /* ── Success / download ── */
        .success-box {
          border: 1px solid var(--border-active); border-radius: 14px;
          padding: 20px 24px;
          background: var(--accent-dim);
          display: flex; align-items: center; gap: 14px;
          animation: popIn 0.3s both;
        }
        .success-icon {
          width: 40px; height: 40px; border-radius: 10px;
          background: rgba(99,211,150,0.2);
          border: 1px solid rgba(99,211,150,0.3);
          display: flex; align-items: center; justify-content: center;
          flex-shrink: 0;
        }
        .success-icon svg {
          width: 20px; height: 20px; stroke: var(--accent);
          fill: none; stroke-width: 2.2; stroke-linecap: round; stroke-linejoin: round;
        }
        .success-text { flex: 1; }
        .success-title { font-size: 13px; font-weight: 500; color: var(--text); }
        .success-sub   { font-size: 11px; color: var(--muted); margin-top: 2px; }

        /* ── Error box ── */
        .error-box {
          border: 1px solid rgba(255,95,109,0.3); border-radius: 14px;
          padding: 14px 18px;
          background: rgba(255,95,109,0.08);
          display: flex; align-items: flex-start; gap: 10px;
          animation: popIn 0.3s both;
        }
        .error-dot {
          width: 8px; height: 8px; border-radius: 50%;
          background: var(--danger); flex-shrink: 0; margin-top: 3px;
        }
        .error-msg { font-size: 12px; color: rgba(255,95,109,0.9); line-height: 1.5; }

        /* ── Buttons ── */
        .btn-row { display: flex; gap: 10px; animation: fadeSlide 0.6s 0.5s both; }

        .cta-btn {
          flex: 1; padding: 15px 20px; border: none; border-radius: 10px;
          font-family: 'Syne', sans-serif; font-size: 15px;
          font-weight: 700; letter-spacing: 0.3px;
          cursor: pointer; transition: all 0.2s ease;
          display: flex; align-items: center; justify-content: center; gap: 8px;
        }
        .cta-btn:disabled {
          background: rgba(255,255,255,0.06); color: var(--muted);
          cursor: not-allowed; border: 1px solid var(--border);
        }
        .cta-btn.primary:not(:disabled) {
          background: var(--accent); color: #08090c;
          box-shadow: 0 0 32px rgba(99,211,150,0.25);
        }
        .cta-btn.primary:not(:disabled):hover {
          background: #7debb0; box-shadow: 0 0 44px rgba(99,211,150,0.4);
          transform: translateY(-1px);
        }
        .cta-btn.download:not(:disabled) {
          background: transparent; color: var(--accent);
          border: 1px solid var(--border-active);
        }
        .cta-btn.download:not(:disabled):hover {
          background: var(--accent-dim); transform: translateY(-1px);
        }
        .cta-btn svg {
          width: 18px; height: 18px; stroke: currentColor;
          fill: none; stroke-width: 2.2; stroke-linecap: round;
        }

        .footer {
          text-align: center; font-size: 11px;
          color: rgba(240,242,245,0.2); letter-spacing: 0.5px;
          position: relative; z-index: 10; margin-top: 24px;
          animation: fadeSlide 0.6s 0.6s both;
        }
      `}</style>

      <div className="root">
        <div className="grid-bg" />
        <div className="blob blob-1" />
        <div className="blob blob-2" />

        <div className="card">
          {/* Header */}
          <div className="header">
            <div className="badge">AI · Data Intelligence</div>
            <h1 className="title">Insight<span>Forge</span></h1>
            <p className="tagline">Let your data tell its story ✨</p>
          </div>

          {/* Drop zone — only when no file picked and not loading/done */}
          {!file && status === "idle" && (
            <div
              className={`dropzone${dragging ? " drag-over" : ""}`}
              onDrop={onDrop}
              onDragOver={onDragOver}
              onDragLeave={onDragLeave}
              onClick={() => inputRef.current.click()}
            >
              <div className="dz-icon">
                <svg viewBox="0 0 24 24">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                  <polyline points="17 8 12 3 7 8"/>
                  <line x1="12" y1="3" x2="12" y2="15"/>
                </svg>
              </div>
              <div className="dz-text">
                <p className="dz-primary">Drop your dataset here, or <strong>browse files</strong></p>
                <p className="dz-secondary">Up to 200 MB per file</p>
              </div>
              <div className="format-chips">
                {ACCEPTED.map(f => <span key={f} className="chip">{f}</span>)}
              </div>
              <input
                ref={inputRef} type="file" style={{ display: "none" }}
                accept={ACCEPTED.map(e => `.${e}`).join(",")}
                onChange={e => handleFile(e.target.files[0])}
              />
            </div>
          )}

          {/* File selected */}
          {file && status !== "loading" && (
            <div className="file-card">
              <div className="file-ext">{file.name.split(".").pop().toUpperCase()}</div>
              <div className="file-info">
                <div className="file-name">{file.name}</div>
                <div className="file-size">{formatSize(file.size)}</div>
              </div>
              <button className="file-remove" onClick={reset} title="Remove file">
                <svg viewBox="0 0 24 24">
                  <line x1="18" y1="6" x2="6" y2="18"/>
                  <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>
          )}

          {/* Loading */}
          {status === "loading" && (
            <div className="loading-box">
              <div className="loading-label">
                <div className="spinner" />
                Turning your data into insights… hang tight!
              </div>
              <div className="progress-track">
                <div className="progress-bar" />
              </div>
            </div>
          )}

          {/* Success + download */}
          {status === "done" && (
            <div className="success-box">
              <div className="success-icon">
                <svg viewBox="0 0 24 24">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
              </div>
              <div className="success-text">
                <div className="success-title">Your insights are ready!</div>
                <div className="success-sub">Click the button below to download your PDF report.</div>
              </div>
            </div>
          )}

          {/* Error */}
          {status === "error" && (
            <div className="error-box">
              <div className="error-dot" />
              <div className="error-msg">{errorMsg}</div>
            </div>
          )}

          {/* Buttons */}
          <div className="btn-row">
            {status !== "done" ? (
              <button
                className="cta-btn primary"
                disabled={!file || status === "loading"}
                onClick={handleActivate}
              >
                <svg viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                {status === "loading" ? "Analyzing…" : "Activate InsightForge"}
              </button>
            ) : (
              <>
                <button className="cta-btn download" onClick={reset}>
                  <svg viewBox="0 0 24 24">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                  New Analysis
                </button>
                <button className="cta-btn primary" onClick={handleDownload}>
                  <svg viewBox="0 0 24 24">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="7 10 12 15 17 10"/>
                    <line x1="12" y1="15" x2="12" y2="3"/>
                  </svg>
                  Download Report
                </button>
              </>
            )}
          </div>
        </div>

        <p className="footer">INSIGHTFORGE · MODULAR DATA INTELLIGENCE PLATFORM</p>
      </div>
    </>
  );
}
