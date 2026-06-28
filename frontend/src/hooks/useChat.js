import { useState } from "react";
import { chatService } from "../services/chatService";
import { useAuth } from "../context/AuthContext";

export function useChat(analysisId) {
  const [messages, setMessages] = useState([
    { sender: "ai", text: "Hi! I'm ready to answer questions about your data." },
  ]);
  const [loading, setLoading] = useState(false);
  const { token } = useAuth();

  const sendMessage = async (text) => {
    if (!text.trim()) return;
    
    setMessages(prev => [...prev, { sender: "user", text }]);
    setLoading(true);

    try {
      const response = await chatService.sendMessage(analysisId, text, token);
      setMessages(prev => [...prev, { sender: "ai", text: response.answer }]);
    } catch (e) {
      setMessages(prev => [...prev, { sender: "ai", text: `Error: ${e.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  return { messages, loading, sendMessage, setMessages };
}
