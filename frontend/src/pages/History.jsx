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

  const renameSession = async (id, currentName) => {
    const newName = window.prompt("Enter new name for this analysis:", currentName);
    if (!newName || newName === currentName) return;

    try {
      const res = await fetch(`${BASE_URL}/sessions/${id}`, {
        method: "PATCH",
        headers: {
          ...authHeaders(),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ name: newName }),
      });
      if (res.ok) {
        setSessions((prev) =>
          prev.map((s) => (s.id === id ? { ...s, filename: newName } : s))
        );
      }
    } catch (e) {
      console.error("Failed to rename session", e);
    }
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
              <div className="history-card-actions">
                <button
                  className="history-card-action-btn"
                  title="Rename"
                  onClick={(e) => {
                    e.stopPropagation();
                    renameSession(s.id, s.filename);
                  }}
                >
                  ✎
                </button>
                <button
                  className="history-card-action-btn delete"
                  title="Delete"
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteSession(s.id);
                  }}
                >
                  ✕
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
