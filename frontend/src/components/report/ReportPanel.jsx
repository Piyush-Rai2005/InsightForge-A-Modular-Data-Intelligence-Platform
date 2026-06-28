import PlotlyChart from "./PlotlyChart";

/**
 * ReportPanel — Schema-aware report with business insights, data-specific charts,
 * and optional ML results. Handles both EDA-only and ML modes.
 */
export default function ReportPanel({ report }) {
  if (!report) return <div className="panel-empty">No report data available.</div>;

  const {
    exec_summary,
    best_model_name,
    best_model_accuracy,
    model_comparison = [],
    recommendations = [],
    visuals = [],
    business_questions,
    visual_narrative,
    key_statistics = [],
    leakage_warnings = [],
    skip_ml,
    skip_ml_reason,
  } = report;

  return (
    <div className="report-panel">
      {/* Skip ML Notice */}
      {skip_ml && (
        <div className="rp-eda-banner">
          <div className="rp-eda-icon">🔍</div>
          <div className="rp-eda-content">
            <div className="rp-eda-title">Exploratory Data Analysis Mode</div>
            <div className="rp-eda-desc">
              {skip_ml_reason || "No suitable ML target found — showing business intelligence insights instead."}
            </div>
          </div>
        </div>
      )}

      {/* Leakage Warnings */}
      {leakage_warnings.length > 0 && (
        <div className="rp-leakage-banner">
          {leakage_warnings.map((w, i) => (
            <div key={i} className="rp-leakage-item">
              <span className="rp-leakage-icon">⚠️</span>
              <span>{w}</span>
            </div>
          ))}
        </div>
      )}

      {/* Executive Summary */}
      {exec_summary && (
        <section className="rp-section">
          <h2 className="rp-section-title">
            <span className="rp-section-icon">📋</span> Executive Summary
          </h2>
          <div className="rp-summary-box">
            <p className="rp-summary-text">{exec_summary}</p>
          </div>
        </section>
      )}

      {/* Key Statistics */}
      {key_statistics.length > 0 && (
        <section className="rp-section">
          <h2 className="rp-section-title">
            <span className="rp-section-icon">📊</span> Key Statistics
          </h2>
          <div className="rp-stats-grid">
            {key_statistics.map((stat, i) => (
              <div key={i} className="rp-stat-card">
                <span className="rp-stat-text">{stat}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Business Questions */}
      {business_questions && (
        <section className="rp-section">
          <h2 className="rp-section-title">
            <span className="rp-section-icon">💡</span> Business Questions Identified
          </h2>
          <div className="rp-questions-box">
            {business_questions.split("\n").filter(q => q.trim()).map((q, i) => (
              <div key={i} className="rp-question-item">{q}</div>
            ))}
          </div>
        </section>
      )}

      {/* Best Model (only if ML ran) */}
      {!skip_ml && best_model_name && (
        <section className="rp-section">
          <h2 className="rp-section-title">
            <span className="rp-section-icon">🏆</span> Best Model
          </h2>
          <div className="rp-best-model">
            <div className="rp-model-badge">
              <span className="rp-model-name">{best_model_name}</span>
              <span className="rp-model-acc">
                {best_model_accuracy != null
                  ? `${(best_model_accuracy * 100).toFixed(2)}% accuracy`
                  : "N/A"}
                {best_model_accuracy > 0.97 && (
                  <span className="rp-leakage-flag"> ⚠️ Possible leakage</span>
                )}
              </span>
            </div>
          </div>
        </section>
      )}

      {/* Model Comparison Table (only if ML ran) */}
      {!skip_ml && model_comparison.length > 0 && (
        <section className="rp-section">
          <h2 className="rp-section-title">
            <span className="rp-section-icon">⚡</span> Model Comparison
          </h2>
          <div className="rp-table-wrap">
            <table className="rp-table">
              <thead>
                <tr>
                  <th>Model</th>
                  <th>Accuracy</th>
                  <th>Performance</th>
                </tr>
              </thead>
              <tbody>
                {model_comparison
                  .slice()
                  .sort((a, b) => b.accuracy - a.accuracy)
                  .map((m, i) => {
                    const pct = (m.accuracy * 100).toFixed(2);
                    const isTop = i === 0;
                    return (
                      <tr key={m.model} className={isTop ? "rp-row--top" : ""}>
                        <td>
                          {isTop && <span className="rp-crown">👑 </span>}
                          {m.model}
                        </td>
                        <td>
                          {pct}%
                          {m.accuracy > 0.97 && <span className="rp-leakage-flag"> ⚠️</span>}
                        </td>
                        <td>
                          <div className="rp-perf-bar-track">
                            <div
                              className="rp-perf-bar"
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Visual Narrative */}
      {visual_narrative && (
        <section className="rp-section">
          <div className="rp-narrative-box">
            <span className="rp-narrative-icon">🔗</span>
            {visual_narrative}
          </div>
        </section>
      )}

      {/* Visualizations — data-specific charts first, then ML charts */}
      {visuals.length > 0 && (
        <section className="rp-section">
          <h2 className="rp-section-title">
            <span className="rp-section-icon">📊</span> Visualizations
          </h2>
          <div className="rp-visuals-grid">
            {visuals.map((v, i) => (
              <div key={i} className="rp-visual-card">
                <div className="rp-visual-header">{v.title}</div>
                <div className="rp-visual-chart">
                  <PlotlyChart
                    spec={v.plotly_spec}
                    image={v.image}
                    title={v.title}
                    height={350}
                  />
                </div>
                {v.insight && (
                  <div className="rp-visual-insight">
                    <span className="rp-insight-dot" />
                    {v.insight}
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Recommendations */}
      {recommendations.length > 0 && (
        <section className="rp-section">
          <h2 className="rp-section-title">
            <span className="rp-section-icon">💡</span> Recommendations
          </h2>
          <ul className="rp-rec-list">
            {recommendations.map((rec, i) => (
              <li key={i} className="rp-rec-item">
                <span className="rp-rec-num">{String(i + 1).padStart(2, "0")}</span>
                <span className="rp-rec-text">{rec}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
