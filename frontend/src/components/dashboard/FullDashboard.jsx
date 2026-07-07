import { useState, useRef, useEffect } from "react";
import TabBar from "./TabBar";
import KpiCard from "./KpiCard";
import TrustGauge from "./TrustGauge";
import PlotlyChart from "../report/PlotlyChart";
import { useChat } from "../../hooks/useChat";
import { useAuth } from "../../context/AuthContext";

const TABS = [
  { id: "quality", icon: "📊", label: "Data Quality" },
  { id: "insights", icon: "💡", label: "Business Insights" },
  { id: "charts", icon: "📈", label: "Visualizations" },
  { id: "chat", icon: "💬", label: "Chat" },
];

/* ── Premium color palette for charts ── */
const CHART_COLORS = [
  '#63d396', '#4ac2dc', '#a78bfa', '#f59e0b', '#ff5f6d',
  '#6ee7b7', '#67e8f9', '#c4b5fd', '#fbbf24', '#fda4af',
];

export default function FullDashboard({ data, analysisId }) {
  const [activeTab, setActiveTab] = useState("quality");

  if (!data) return null;

  const report = data.report || {};
  const dashboard = data.dashboard || {};
  const health = data.health_report || {};
  const trustScore = data.trust_score || 0;
  const advanced = data.advanced_insights || {};

  return (
    <div className="fd-root">
      <TabBar tabs={TABS} activeTab={activeTab} onChange={setActiveTab} />
      <div className="fd-content">
        {activeTab === "quality" && (
          <QualityTab report={report} dashboard={dashboard} health={health} trustScore={trustScore} />
        )}
        {activeTab === "insights" && (
          <InsightsTab report={report} advanced={advanced} />
        )}
        {activeTab === "charts" && (
          <ChartsTab report={report} />
        )}
        {activeTab === "chat" && (
          <ChatTab analysisId={analysisId} />
        )}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   TAB 1: Data Quality & Overview
═══════════════════════════════════════════════════════════════════════════ */
function QualityTab({ report, dashboard, health, trustScore }) {
  const overview = report.dataset_overview || {};
  const missingValues = report.missing_values || [];
  const kpis = dashboard.kpis || {};

  const missingPct = overview.rows
    ? ((missingValues.reduce((sum, m) => sum + m.missing, 0) / (overview.rows * overview.columns)) * 100).toFixed(1)
    : "0";

  // Build missing values Plotly chart with gradient-style bars
  const missingChart = missingValues.length > 0 ? {
    data: [{
      type: "bar",
      x: missingValues.map(m => m.column),
      y: missingValues.map(m => m.missing),
      marker: {
        color: missingValues.map((m, i) => {
          if (m.missing > (overview.rows * 0.3)) return '#ff5f6d';
          if (m.missing > (overview.rows * 0.1)) return '#f59e0b';
          return CHART_COLORS[i % CHART_COLORS.length];
        }),
        line: { width: 0 },
        opacity: 0.85,
      },
      hovertemplate: "<b>%{x}</b><br>%{y} missing<extra></extra>",
    }],
    layout: {
      title: { text: "Missing Values by Column", font: { color: "#eaedf3", size: 14 } },
      xaxis: { tickangle: -45 },
      margin: { l: 50, r: 20, t: 44, b: 100 },
    }
  } : null;

  // Data types breakdown
  const descRows = overview.desc_rows || [];
  const descCols = overview.desc_cols || [];

  return (
    <div className="fd-tab fd-tab--quality">
      {/* KPI Row */}
      <div className="fd-kpi-row">
        <KpiCard icon="📋" label="Total Rows" value={overview.rows?.toLocaleString()} color="rgba(99,211,150,0.1)" />
        <KpiCard icon="📊" label="Total Columns" value={overview.columns} color="rgba(74,194,220,0.1)" />
        <KpiCard icon="⚠️" label="Missing Data" value={`${missingPct}%`} subtitle={`${missingValues.length} columns affected`} color="rgba(245,158,11,0.1)" />
        <KpiCard icon="🏆" label="Best Model" value={kpis.best_model || "—"} subtitle={kpis.best_model_accuracy != null ? `${(kpis.best_model_accuracy * 100).toFixed(1)}% accuracy` : "EDA mode"} color="rgba(167,139,250,0.1)" />
      </div>

      {/* Trust Score + Health */}
      <div className="fd-row">
        <div className="fd-card fd-card--gauge">
          <h3 className="fd-card-title">Data Trust Score</h3>
          <TrustGauge score={trustScore} />
          <p className="fd-card-desc">
            {trustScore >= 80 ? "This dataset has excellent quality and is ready for analysis." :
             trustScore >= 50 ? "Some quality issues detected — results may need verification." :
             "Significant quality concerns found — interpret results with caution."}
          </p>
        </div>

        {/* Health Summary */}
        <div className="fd-card fd-card--health">
          <h3 className="fd-card-title">🩺 Data Health Summary</h3>
          {health.missing_cells != null && (
            <div className="fd-health-stat">
              <span className="fd-health-label">Missing Cells</span>
              <span className="fd-health-value">{health.missing_cells}</span>
            </div>
          )}
          {health.anomalies && health.anomalies.length > 0 ? (
            <div className="fd-anomalies">
              <div className="fd-anomaly-title">⚠️ Detected Anomalies</div>
              {health.anomalies.map((a, i) => (
                <div key={i} className="fd-anomaly-item">{a}</div>
              ))}
            </div>
          ) : (
            <div className="fd-health-ok">✓ No major anomalies detected</div>
          )}
        </div>
      </div>

      {/* Missing Values Chart */}
      {missingChart && (
        <div className="fd-card">
          <PlotlyChart spec={missingChart} height={300} />
        </div>
      )}

      {/* Descriptive Statistics Table */}
      {descRows.length > 0 && (
        <div className="fd-card">
          <h3 className="fd-card-title">📋 Descriptive Statistics</h3>
          <div className="fd-table-wrap">
            <table className="fd-table">
              <thead>
                <tr>
                  <th>Feature</th>
                  {descCols.map((c) => <th key={c}>{c}</th>)}
                </tr>
              </thead>
              <tbody>
                {descRows.map((row, i) => (
                  <tr key={i}>
                    <td className="fd-table-feature">{row.feature}</td>
                    {descCols.map((c) => <td key={c}>{row[c]}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   TAB 2: Business Insights
═══════════════════════════════════════════════════════════════════════════ */
function InsightsTab({ report, advanced }) {
  const {
    exec_summary,
    recommendations = [],
    business_questions,
    key_statistics = [],
    leakage_warnings = [],
    skip_ml,
    skip_ml_reason,
    visual_narrative,
  } = report;

  const summary = advanced?.summary || {};
  const sensitivity = advanced?.sensitivity_analysis || {};
  const temporal = advanced?.temporal_intelligence || {};

  return (
    <div className="fd-tab fd-tab--insights">
      {/* EDA Mode Notice */}
      {skip_ml && (
        <div className="fd-banner fd-banner--info">
          <span className="fd-banner-icon">🔍</span>
          <div>
            <strong>Exploratory Data Analysis Mode</strong>
            <p>{skip_ml_reason || "No suitable ML target found — showing business intelligence insights instead."}</p>
          </div>
        </div>
      )}

      {/* Leakage Warnings */}
      {leakage_warnings.length > 0 && (
        <div className="fd-banner fd-banner--danger">
          {leakage_warnings.map((w, i) => (
            <div key={i} className="fd-banner-item">⚠️ {w}</div>
          ))}
        </div>
      )}

      {/* Executive Summary */}
      {exec_summary && (
        <div className="fd-card fd-card--highlight">
          <h3 className="fd-card-title">📋 Executive Summary</h3>
          <p className="fd-summary-text">{exec_summary}</p>
        </div>
      )}

      {/* For the Manager */}
      <div className="fd-card">
        <h3 className="fd-card-title">
          <span className="fd-badge fd-badge--manager">For Managers</span>
          What This Means for Your Business
        </h3>
        <div className="fd-insight-list">
          {(summary.executive_summary || []).length > 0 ? (
            summary.executive_summary.map((item, i) => (
              <div key={i} className="fd-insight-item fd-insight-item--manager">
                <span className="fd-insight-num">{String(i + 1).padStart(2, "0")}</span>
                <span>{item}</span>
              </div>
            ))
          ) : (
            recommendations.slice(0, 5).map((rec, i) => (
              <div key={i} className="fd-insight-item fd-insight-item--manager">
                <span className="fd-insight-num">{String(i + 1).padStart(2, "0")}</span>
                <span>{rec}</span>
              </div>
            ))
          )}
        </div>
      </div>

      {/* For the Data Scientist */}
      {key_statistics.length > 0 && (
        <div className="fd-card">
          <h3 className="fd-card-title">
            <span className="fd-badge fd-badge--ds">For Data Scientists</span>
            Technical Deep-Dive
          </h3>
          <div className="fd-stats-grid">
            {key_statistics.map((stat, i) => (
              <div key={i} className="fd-stat-card">{stat}</div>
            ))}
          </div>
        </div>
      )}

      {/* What-If Scenarios */}
      {sensitivity.simulations && sensitivity.simulations.length > 0 && (
        <div className="fd-card">
          <h3 className="fd-card-title">🔮 What-If Scenarios</h3>
          {sensitivity.simulations.map((sim, i) => (
            <div key={i} className="fd-insight-item fd-insight-item--scenario">{sim}</div>
          ))}
        </div>
      )}

      {/* Business Questions */}
      {business_questions && (
        <div className="fd-card">
          <h3 className="fd-card-title">❓ Business Questions This Data Can Answer</h3>
          <div className="fd-questions-list">
            {business_questions.split("\n").filter(q => q.trim()).map((q, i) => (
              <div key={i} className="fd-question-item">{q}</div>
            ))}
          </div>
        </div>
      )}

      {/* Visual Narrative */}
      {visual_narrative && (
        <div className="fd-card fd-card--narrative">
          <span className="fd-narrative-icon">🔗</span>
          {visual_narrative}
        </div>
      )}

      {/* Recommendations */}
      {recommendations.length > 0 && (
        <div className="fd-card">
          <h3 className="fd-card-title">💡 Actionable Recommendations</h3>
          <div className="fd-rec-list">
            {recommendations.map((rec, i) => (
              <div key={i} className="fd-rec-item">
                <span className="fd-rec-priority">
                  {i < 2 ? "HIGH" : i < 4 ? "MED" : "LOW"}
                </span>
                <span className="fd-rec-text">{rec}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   TAB 3: Visualizations & Models
═══════════════════════════════════════════════════════════════════════════ */
function ChartsTab({ report }) {
  const {
    visuals = [],
    model_comparison = [],
    best_model_name,
    best_model_accuracy,
    skip_ml,
    skip_ml_reason,
  } = report;

  // Build a model comparison donut chart
  const modelDonut = !skip_ml && model_comparison.length > 0 ? {
    data: [{
      type: "pie",
      labels: model_comparison.map(m => m.model),
      values: model_comparison.map(m => m.accuracy),
      hole: 0.55,
      marker: {
        colors: CHART_COLORS.slice(0, model_comparison.length),
        line: { color: 'rgba(6,8,16,0.8)', width: 2 },
      },
      textinfo: "label+percent",
      textfont: { color: '#eaedf3', size: 11 },
      hovertemplate: "<b>%{label}</b><br>Accuracy: %{value:.2%}<extra></extra>",
      sort: false,
    }],
    layout: {
      title: { text: "Model Accuracy Distribution", font: { color: "#eaedf3", size: 14 } },
      margin: { l: 20, r: 20, t: 44, b: 20 },
      showlegend: true,
      legend: { font: { color: 'rgba(234,237,243,0.6)', size: 11 } },
    }
  } : null;

  return (
    <div className="fd-tab fd-tab--charts">
      {skip_ml && (
        <div className="fd-banner fd-banner--info">
          <span className="fd-banner-icon">🔍</span>
          <div>
            <strong>EDA Mode</strong>
            <p>{skip_ml_reason || "Charts below are from exploratory data analysis."}</p>
          </div>
        </div>
      )}

      {/* Best Model Badge */}
      {!skip_ml && best_model_name && (
        <div className="fd-card fd-card--model-badge">
          <div className="fd-model-crown">🏆</div>
          <div className="fd-model-info">
            <div className="fd-model-name">{best_model_name}</div>
            <div className="fd-model-acc">
              {best_model_accuracy != null ? `${(best_model_accuracy * 100).toFixed(2)}% accuracy` : "N/A"}
              {best_model_accuracy > 0.97 && <span className="fd-leakage-flag"> ⚠️ Possible leakage</span>}
            </div>
          </div>
        </div>
      )}

      {/* Model Comparison — Table + Donut */}
      {!skip_ml && model_comparison.length > 0 && (
        <div className="fd-row">
          <div className="fd-card">
            <h3 className="fd-card-title">⚡ Model Comparison</h3>
            <div className="fd-table-wrap">
              <table className="fd-table">
                <thead>
                  <tr><th>Model</th><th>Accuracy</th><th>Performance</th></tr>
                </thead>
                <tbody>
                  {model_comparison.sort((a, b) => b.accuracy - a.accuracy).map((m, i) => {
                    const pct = (m.accuracy * 100).toFixed(2);
                    return (
                      <tr key={m.model} className={i === 0 ? "fd-row--top" : ""}>
                        <td>{i === 0 && "👑 "}{m.model}</td>
                        <td>{pct}%{m.accuracy > 0.97 && <span className="fd-leakage-flag"> ⚠️</span>}</td>
                        <td>
                          <div className="fd-perf-track">
                            <div className="fd-perf-bar" style={{ width: `${pct}%` }} />
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Donut chart */}
          {modelDonut && (
            <div className="fd-card">
              <PlotlyChart spec={modelDonut} height={300} />
            </div>
          )}
        </div>
      )}

      {/* All Charts */}
      {visuals.length > 0 ? (
        <div className="fd-charts-grid">
          {visuals.map((v, i) => (
            <div key={i} className="fd-chart-card">
              <div className="fd-chart-header">
                <span style={{ opacity: 0.6 }}>📊</span>
                {v.title}
              </div>
              <div className="fd-chart-body">
                <PlotlyChart spec={v.plotly_spec} image={v.image} title={v.title} height={380} />
              </div>
              {v.insight && (
                <div className="fd-chart-insight">
                  <span className="fd-insight-dot" />
                  {v.insight}
                </div>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="fd-empty-state">
          <span>📊</span>
          <p>No visualizations generated for this dataset.</p>
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   TAB 4: Chat with Your Data
═══════════════════════════════════════════════════════════════════════════ */
function ChatTab({ analysisId }) {
  const { messages, loading, sendMessage } = useChat(analysisId);
  const chatEndRef = useRef(null);
  const [input, setInput] = useState("");

  const suggestedQuestions = [
    "What are the key trends in this data?",
    "Which columns have the most missing values?",
    "What's the distribution of the main metric?",
    "Are there any outliers I should investigate?",
  ];

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim()) {
      sendMessage(input.trim());
      setInput("");
    }
  };

  const handleSuggestion = (q) => {
    sendMessage(q);
  };

  return (
    <div className="fd-tab fd-tab--chat">
      <div className="fd-chat-container">
        <div className="fd-chat-messages">
          {messages.map((m, i) => (
            <div key={i} className={`fd-msg fd-msg--${m.sender}`}>
              {m.sender === "ai" && <div className="fd-msg-avatar">🤖</div>}
              <div className="fd-msg-bubble">{m.text}</div>
            </div>
          ))}
          {loading && (
            <div className="fd-msg fd-msg--ai">
              <div className="fd-msg-avatar">🤖</div>
              <div className="fd-msg-bubble fd-msg--typing">
                <span /><span /><span />
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Suggested Questions (only show if few messages) */}
        {messages.length <= 2 && (
          <div className="fd-suggestions">
            {suggestedQuestions.map((q, i) => (
              <button key={i} className="fd-suggestion-btn" onClick={() => handleSuggestion(q)}>
                {q}
              </button>
            ))}
          </div>
        )}

        <form onSubmit={handleSubmit} className="fd-chat-input-area">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            type="text"
            className="fd-chat-input"
            placeholder="Ask a question about your data..."
            autoComplete="off"
            disabled={loading}
          />
          <button type="submit" className="fd-chat-btn" disabled={loading || !input.trim()}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </form>
      </div>
    </div>
  );
}
