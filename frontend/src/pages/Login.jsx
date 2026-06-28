import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";

export default function Login() {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const { login, register, loading, error } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (isRegister) {
        await register(email, password, displayName);
      } else {
        await login(email, password);
      }
      navigate("/");
    } catch {
      // error is set in context
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo">InsightForge</div>
        <h2 className="auth-title">{isRegister ? "Create Account" : "Welcome Back"}</h2>

        <form onSubmit={handleSubmit} className="auth-form">
          {isRegister && (
            <input
              type="text"
              placeholder="Display Name"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="auth-input"
            />
          )}
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="auth-input"
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="auth-input"
          />
          {error && <div className="auth-error">{error}</div>}
          <button type="submit" className="auth-btn" disabled={loading}>
            {loading ? "..." : isRegister ? "Register" : "Sign In"}
          </button>
        </form>

        <div className="auth-switch">
          {isRegister ? "Already have an account?" : "Need an account?"}{" "}
          <button
            className="auth-switch-btn"
            onClick={() => setIsRegister(!isRegister)}
          >
            {isRegister ? "Sign In" : "Register"}
          </button>
        </div>
      </div>
    </div>
  );
}
