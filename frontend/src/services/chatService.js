const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const chatService = {
  async sendMessage(analysisId, question, token) {
    const headers = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const res = await fetch(`${BASE_URL}/chat`, {
      method: "POST",
      headers,
      body: JSON.stringify({ analysis_id: analysisId, question }),
    });
    
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Chat failed");
    return data;
  }
};
