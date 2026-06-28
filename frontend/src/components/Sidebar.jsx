import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

function timeAgo(dateStr) {
  const now = new Date();
  const d = new Date(dateStr);
  const diff = (now - d) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return d.toLocaleDateString();
}

function groupByDate(sessions) {
  const groups = { Today: [], Yesterday: [], "Previous 7 Days": [], Older: [] };
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today - 86400000);
  const weekAgo = new Date(today - 7 * 86400000);

  sessions.forEach((s) => {
    const d = new Date(s.created_at);
    if (d >= today) groups.Today.push(s);
    else if (d >= yesterday) groups.Yesterday.push(s);
    else if (d >= weekAgo) groups["Previous 7 Days"].push(s);
    else groups.Older.push(s);
  });

  return Object.entries(groups).filter(([, items]) => items.length > 0);
}

export default function Sidebar({ collapsed, onToggle }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, token, logout, authHeaders } = useAuth();
  const [sessions, setSessions] = useState([]);
  const [menuOpen, setMenuOpen] = useState(null);

  useEffect(() => {
    if (!token) return;
    fetch(`${BASE_URL}/sessions`, { headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : []))
      .then(setSessions)
      .catch(() => {});
  }, [token, authHeaders, location.pathname]);

  const handleDelete = async (e, id) => {
    e.stopPropagation();
    setMenuOpen(null);
    await fetch(`${BASE_URL}/sessions/${id}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    setSessions((prev) => prev.filter((s) => s.id !== id));
  };

  const activeId = location.pathname.startsWith("/dashboard/")
    ? location.pathname.split("/dashboard/")[1]
    : null;

  const grouped = groupByDate(sessions);

  return (
    <aside className={`sidebar ${collapsed ? "sidebar--collapsed" : ""}`}>
      {/* Top */}
      <div className="sb-top">
        <button className="sb-toggle" onClick={onToggle} title="Toggle sidebar">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>
        {!collapsed && (
          <span className="sb-brand" onClick={() => navigate("/")}>
            InsightForge
          </span>
        )}
      </div>

      {!collapsed && (
        <button className="sb-new-btn" onClick={() => navigate("/")}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          New Analysis
        </button>
      )}

      {/* Session History */}
      {!collapsed && (
        <div className="sb-sessions">
          {!token ? (
            <div className="sb-signin-prompt">
              <p>Sign in to save your analysis history</p>
              <button className="sb-signin-btn" onClick={() => navigate("/login")}>
                Sign In
              </button>
            </div>
          ) : sessions.length === 0 ? (
            <div className="sb-empty">
              <span className="sb-empty-icon">📂</span>
              <p>No analyses yet</p>
            </div>
          ) : (
            grouped.map(([label, items]) => (
              <div key={label} className="sb-group">
                <div className="sb-group-label">{label}</div>
                {items.map((s) => (
                  <div
                    key={s.id}
                    className={`sb-item ${activeId === s.id ? "sb-item--active" : ""}`}
                    onClick={() => navigate(`/dashboard/${s.id}`)}
                  >
                    <svg className="sb-item-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                      <polyline points="14 2 14 8 20 8" />
                    </svg>
                    <span className="sb-item-name">{s.filename}</span>
                    <span className="sb-item-time">{timeAgo(s.created_at)}</span>

                    <button
                      className="sb-item-menu"
                      onClick={(e) => {
                        e.stopPropagation();
                        setMenuOpen(menuOpen === s.id ? null : s.id);
                      }}
                    >
                      ⋯
                    </button>

                    {menuOpen === s.id && (
                      <div className="sb-item-dropdown">
                        <button onClick={(e) => handleDelete(e, s.id)}>🗑️ Delete</button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ))
          )}
        </div>
      )}

      {/* Bottom */}
      {!collapsed && token && user && (
        <div className="sb-bottom">
          <div className="sb-user">
            <div className="sb-avatar">{(user.display_name || user.email || "U")[0].toUpperCase()}</div>
            <span className="sb-user-name">{user.display_name || user.email}</span>
          </div>
          <button className="sb-logout" onClick={logout}>
            Sign Out
          </button>
        </div>
      )}
    </aside>
  );
}
