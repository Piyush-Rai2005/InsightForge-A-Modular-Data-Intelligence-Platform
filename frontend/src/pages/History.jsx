import { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function History() {
  const { authHeaders, user } = useAuth();
  const navigate = useNavigate();
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${BASE_URL}/sessions`, { headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : []))
      .then(setSessions)
      .catch(() => setSessions([]))
      .finally(() => setLoading(false));
  }, [authHeaders]);

  const deleteSession = async (id) => {
    await fetch(`${BASE_URL}/sessions/${id}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    setSessions((prev) => prev.filter((s) => s.id !== id));
  };

  if (loading) return <div className="history-loading">Loading sessions...</div>;

  return (
    <div className="history-page">
      <div className="history-header">
        <h1 className="history-title">Analysis History</h1>
        <button className="history-back-btn" onClick={() => navigate("/")}>
          + New Analysis
        </button>
      </div>

      {sessions.length === 0 ? (
        <div className="history-empty">
          <div className="history-empty-icon">📊</div>
          <p>No previous analyses found. Upload a dataset to get started!</p>
        </div>
      ) : (
        <div className="history-grid">
          {sessions.map((s) => (
            <div
              key={s.id}
              className="history-card"
              onClick={() => navigate(`/dashboard/${s.id}`)}
            >
              <div className="history-card-icon">📄</div>
              <div className="history-card-info">
                <div className="history-card-name">{s.filename}</div>
                <div className="history-card-date">
                  {new Date(s.created_at).toLocaleDateString()}
                </div>
                {s.schedule_frequency && (
                  <div className="history-card-schedule">
                    🔄 {s.schedule_frequency}
                  </div>
                )}
              </div>
              <button
                className="history-card-delete"
                onClick={(e) => {
                  e.stopPropagation();
                  deleteSession(s.id);
                }}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
