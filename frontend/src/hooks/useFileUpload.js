import { useState, useRef } from "react";
import { useAuth } from "../context/AuthContext";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function useFileUpload() {
  const [jobId, setJobId] = useState(null);
  const [status, setStatus] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [isCancelling, setIsCancelling] = useState(false);
  const { authHeaders } = useAuth();

  // Ref-based flag: avoids stale closures in the polling recursion.
  // When set to true the next setTimeout callback exits immediately.
  const cancelledRef = useRef(false);

  const uploadFile = async (file) => {
    cancelledRef.current = false;
    setJobId(null);
    setStatus({ status: "queued", step: "Uploading file...", progress: 0 });
    setError("");
    setResult(null);
    setIsCancelling(false);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${BASE_URL}/analyze`, {
        method: "POST",
        headers: authHeaders(),
        body: formData,
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Upload failed");

      setJobId(data.job_id);
      pollStatus(data.job_id);
    } catch (e) {
      setError(e.message);
      setStatus(null);
    }
  };

  const cancelAnalysis = async (id) => {
    if (!id || isCancelling) return;
    setIsCancelling(true);

    // Stop the polling loop immediately
    cancelledRef.current = true;

    try {
      await fetch(`${BASE_URL}/jobs/${id}`, {
        method: "DELETE",
        headers: authHeaders(),
      });
    } catch (_) {
      // Ignore network errors on cancel — the ref already stopped polling
    }

    setStatus(null);
    setError("");
    setJobId(null);
    setIsCancelling(false);
  };

  const pollStatus = async (id, attempt = 0) => {
    // Stop immediately if user cancelled
    if (cancelledRef.current) return;

    // Hard cap: stop after ~2 minutes regardless of server state
    const MAX_ATTEMPTS = 80;
    if (attempt >= MAX_ATTEMPTS) {
      setError("Analysis is taking too long. Please try again.");
      setStatus(null);
      return;
    }

    try {
      const res = await fetch(`${BASE_URL}/jobs/${id}/status`, {
        headers: authHeaders(),
      });
      const data = await res.json();

      setStatus({ status: data.status, step: data.step, progress: data.progress });

      if (data.status === "error") {
        setError(data.step || "Job failed");
        return;
      }
      if (data.status === "done") {
        fetchResult(id);
        return;
      }
      if (data.status === "cancelled") {
        setStatus(null);
        return;
      }

      // Back-off after 20 polls (30s): 1.5s → 3s
      const delay = attempt > 20 ? 3000 : 1500;
      setTimeout(() => pollStatus(id, attempt + 1), delay);
    } catch (e) {
      setError("Lost connection to server");
    }
  };

  const fetchResult = async (id) => {
    try {
      const res = await fetch(`${BASE_URL}/jobs/${id}/result`, {
        headers: authHeaders(),
      });
      const data = await res.json();

      if (!res.ok) throw new Error(data.detail || "Failed to fetch result");

      setResult(data);
    } catch (e) {
      setError(e.message);
    }
  };

  return { uploadFile, cancelAnalysis, status, result, error, jobId, isCancelling };
}
