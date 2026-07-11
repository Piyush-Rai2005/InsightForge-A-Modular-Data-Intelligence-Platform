import { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import Sidebar from "./components/Sidebar";
import Home from "./pages/Home";
import Dashboard from "./pages/Dashboard";
import Login from "./pages/Login";
import History from "./pages/History";
import "./index.css";

function ProtectedRoute({ children }) {
  const { token, loading } = useAuth();
  if (loading) return <div className="loading-screen">Loading...</div>;
  if (!token) return <Navigate to="/login" replace />;
  return children;
}

function TopBar() {
  const { user, token, logout } = useAuth();
  const [dropdownOpen, setDropdownOpen] = useState(false);

  if (!token) {
    return (
      <div className="topbar">
        <a href="/login" className="topbar-signin">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" />
            <polyline points="10 17 15 12 10 7" />
            <line x1="15" y1="12" x2="3" y2="12" />
          </svg>
          Sign In
        </a>
      </div>
    );
  }

  const initial = (user?.display_name || user?.email || "U")[0].toUpperCase();

  return (
    <div className="topbar">
      <button
        className="topbar-avatar"
        onClick={() => setDropdownOpen(!dropdownOpen)}
        onBlur={() => setTimeout(() => setDropdownOpen(false), 150)}
      >
        {initial}
      </button>
      {dropdownOpen && (
        <div className="topbar-dropdown">
          <div className="topbar-dropdown-name">{user?.display_name || user?.email}</div>
          <div className="topbar-dropdown-email">{user?.email}</div>
          <div className="topbar-dropdown-divider" />
          <button className="topbar-dropdown-btn" onClick={logout}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
            Sign Out
          </button>
        </div>
      )}
    </div>
  );
}

function AppShell() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  
  // Theme state
  const [isLightMode, setIsLightMode] = useState(() => {
    return localStorage.getItem("theme") === "light";
  });

  useEffect(() => {
    if (isLightMode) {
      document.body.classList.add("light-mode");
      localStorage.setItem("theme", "light");
    } else {
      document.body.classList.remove("light-mode");
      localStorage.setItem("theme", "dark");
    }
  }, [isLightMode]);

  return (
    <div className="app-shell">
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
        isLightMode={isLightMode}
        onToggleTheme={() => setIsLightMode(!isLightMode)}
      />
      <main className={`app-main ${sidebarCollapsed ? "app-main--expanded" : ""}`}>
        <TopBar />
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<Home />} />
          <Route
            path="/history"
            element={
              <ProtectedRoute>
                <History />
              </ProtectedRoute>
            }
          />
          <Route
            path="/dashboard/:id"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
        </Routes>
      </main>
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppShell />
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;