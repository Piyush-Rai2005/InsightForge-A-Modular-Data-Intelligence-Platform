export default function KpiCard({ icon, label, value, subtitle, color }) {
  return (
    <div className="kpi-card">
      <div className="kpi-icon" style={{ background: `${color || "rgba(99,211,150,0.12)"}` }}>
        {icon}
      </div>
      <div className="kpi-info">
        <div className="kpi-label">{label}</div>
        <div className="kpi-value">{value ?? "—"}</div>
        {subtitle && <div className="kpi-subtitle">{subtitle}</div>}
      </div>
    </div>
  );
}
