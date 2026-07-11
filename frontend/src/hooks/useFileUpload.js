import { useState } from "react";
import { useAuth } from "../context/AuthContext";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function useFileUpload() {
  const [jobId, setJobId] = useState(null);
  const [status, setStatus] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const { authHeaders } = useAuth();

  const uploadFile = async (file) => {
    setJobId(null);
    setStatus({ status: "queued", step: "Uploading file...", progress: 0 });
    setError("");
    setResult(null);

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

  const pollStatus = async (id) => {
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

      setTimeout(() => pollStatus(id), 1500);
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

  return { uploadFile, status, result, error, jobId };
}
