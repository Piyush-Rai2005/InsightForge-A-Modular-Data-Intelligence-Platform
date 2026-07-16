import { useRef, useState } from "react";
import { useFileUpload } from "../hooks/useFileUpload";
import { useAuth } from "../context/AuthContext";
import LoadingCard from "../components/report/LoadingCard";
import FullDashboard from "../components/dashboard/FullDashboard";

export default function Home() {
  const fileInput = useRef(null);
  const { uploadFile, cancelAnalysis, status, result, error, jobId, isCancelling } = useFileUpload();
  const { user } = useAuth();
  const [fileName, setFileName] = useState("");
  const [dragging, setDragging] = useState(false);

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) {
      setFileName(file.name);
      uploadFile(file);
    }
  };

  const handleSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      setFileName(file.name);
      uploadFile(file);
    }
  };

  const hasResult = result && status?.status === "done";

  return (
    <div className="home-page">
      {/* Upload Section */}
      {!hasResult ? (
        <div className="home-upload-section">
          <div className="hero-section">
            <div className="hero-badge">AI · Data Intelligence</div>
            <h1 className="hero-title">
              <span className="hero-text-white">Insight</span>
              <span className="hero-text-accent">Forge</span>
            </h1>
            <p className="hero-subtitle">Upload your data. Get instant business intelligence.</p>
          </div>

          <div className="upload-card">
            {error && (
              <div className="upload-error">
                <span className="upload-error-dot" />
                {error}
              </div>
            )}

            {status && status.status !== "error" && status.status !== "done" ? (
              <div className="loading-section">
                <LoadingCard status={status} progress={status.progress} />
                <button
                  id="cancel-analysis-btn"
                  className="cancel-analysis-btn"
                  onClick={() => cancelAnalysis(jobId)}
                  disabled={isCancelling}
                >
                  {isCancelling ? (
                    <>
                      <span className="cancel-spinner" />
                      Cancelling...
                    </>
                  ) : (
                    <>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                        <line x1="18" y1="6" x2="6" y2="18" />
                        <line x1="6" y1="6" x2="18" y2="18" />
                      </svg>
                      Cancel Analysis
                    </>
                  )}
                </button>
              </div>
            ) : (
              <div
                className={`drop-zone${dragging ? " drag-over" : ""}`}
                onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={handleDrop}
              >
                <div className="dz-icon-wrap">
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="17 8 12 3 7 8" />
                    <line x1="12" y1="3" x2="12" y2="15" />
                  </svg>
                </div>
                <h3 className="dz-title">Drag & Drop your dataset here</h3>
                <p className="dz-subtitle">
                  Supports CSV, Excel, SQLite, JSON, Parquet, XML, YAML, ZIP
                </p>
                <input
                  type="file"
                  ref={fileInput}
                  className="file-input"
                  onChange={handleSelect}
                />
                <button className="upload-btn" onClick={() => fileInput.current.click()}>
                  Browse Files
                </button>
              </div>
            )}
          </div>
        </div>
      ) : (
        /* Results Section */
        <div className="home-results-section">
          <div className="results-header">
            <div className="results-file-info">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
              <span>{fileName}</span>
            </div>
            <button className="results-new-btn" onClick={() => window.location.reload()}>
              + New Analysis
            </button>
          </div>
          <FullDashboard data={result} analysisId={jobId} />
        </div>
      )}
    </div>
  );
}
