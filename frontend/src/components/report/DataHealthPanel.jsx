export default function DataHealthPanel({ health, trustScore }) {
  if (!health) return null;

  return (
    <section className="rp-section">
      <h2 className="rp-section-title">
        <span className="rp-section-icon">🩺</span> Data Health
      </h2>
      <div style={{ background: "rgba(255,255,255,0.02)", padding: "20px", borderRadius: "12px", border: "1px solid var(--border)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "16px" }}>
          <div>
            <strong>Missing Cells:</strong> {health.missing_cells}
          </div>
          <div>
            <strong>Trust Score:</strong> 
            <span style={{ 
              color: trustScore > 80 ? "var(--accent)" : trustScore > 50 ? "#f59e0b" : "#ff5f6d",
              marginLeft: "8px",
              fontWeight: "bold"
            }}>
              {trustScore}/100
            </span>
          </div>
        </div>

        {health.anomalies && health.anomalies.length > 0 ? (
          <div>
            <h4 style={{ marginBottom: "8px", color: "var(--muted)" }}>Detected Anomalies</h4>
            <ul style={{ listStyle: "inside", fontSize: "13px" }}>
              {health.anomalies.map((a, i) => (
                <li key={i} style={{ marginBottom: "4px" }}>{a}</li>
              ))}
            </ul>
          </div>
        ) : (
          <div style={{ color: "var(--accent)", fontSize: "13px" }}>
            ✓ No major anomalies detected.
          </div>
        )}
      </div>
    </section>
  );
}
