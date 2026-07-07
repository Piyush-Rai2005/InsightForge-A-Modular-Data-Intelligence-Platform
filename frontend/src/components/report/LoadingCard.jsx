export default function LoadingCard({ status, progress = 0 }) {
  const messages = {
    queued: "Waiting in queue...",
    running: "Analyzing dataset...",
    error: "Analysis failed",
    done: "Finishing up...",
  };

  const currentMsg = messages[status?.status] || "Connecting...";
  const stepText = status?.step || "";
  const pct = Math.round(progress * 100);

  return (
    <div className="loading-card">
      <div className="spinner" />
      <h3 style={{ marginBottom: "8px", fontWeight: 600, fontSize: "16px" }}>{currentMsg}</h3>
      <p style={{ color: "var(--muted)", fontSize: "13px" }}>
        {stepText}
      </p>
      {status?.status === "running" && (
        <div className="loading-progress">
          <div className="loading-bar" style={{ width: `${pct}%` }} />
        </div>
      )}
    </div>
  );
}
