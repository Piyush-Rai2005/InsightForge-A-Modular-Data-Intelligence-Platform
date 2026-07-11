import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import FullDashboard from "../components/dashboard/FullDashboard";
import { useAuth } from "../context/AuthContext";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function Dashboard() {
  const { id } = useParams();
  const { authHeaders } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${BASE_URL}/sessions/${id}`, { headers: authHeaders() })
      .then((r) => {
        if (!r.ok) throw new Error("Session not found");
        return r.json();
      })
      .then((session) => {
        // Reshape session data to match FullDashboard's expected format
        setData({
          report: session.report || {},
          dashboard: session.dashboard || {},
          health_report: session.health_report || {},
          trust_score: session.trust_score || 0,
          advanced_insights: session.advanced_insights || {},
        });
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id, authHeaders]);

  if (loading) {
    return (
      <div className="fd-loading">
        <div className="spinner" />
        <p>Loading analysis...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="fd-error">
        <span>❌</span>
        <p>{error}</p>
      </div>
    );
  }

  return (
    <div className="dashboard-page">
      <FullDashboard data={data} analysisId={id} />
    </div>
  );
}
