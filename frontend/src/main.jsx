// Start of the React app: asks the server who is logged in, then shows the right page.
// The server checks the login and the role again on every /api call: this is only for display.
import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { api, me } from "./api.js";
import Chat from "./pages/Chat.jsx";
import Login from "./pages/Login.jsx";
import "./style.css";

function App() {
  const [info, setInfo] = useState(null);          // answer of GET /api/me

  useEffect(() => { me().then(setInfo); }, []);
  if (!info) return <p className="muted" style={{ padding: 20 }}>Loading…</p>;

  async function logout() {
    await api("/logout", {});
    await me().then(setInfo);                      // a new CSRF token for the next login
  }

  const user = info.user;
  return (
    <>
      <header>
        <span className="brand">Verdicta</span>
        <span className="muted" style={{ color: "#c9d6e8" }}>{info.coverage}</span>
        {user && <span>{user.email}</span>}
        {user?.role === "admin" && <a href="/admin">Admin</a>}
        {user && <button className="link" onClick={logout}>Log out</button>}
      </header>
      <main>
        <Routes>
          <Route path="/login" element={user ? <Navigate to="/" /> :
            <Login onLogin={(u) => setInfo({ ...info, user: u })} />} />
          <Route path="/" element={user ? <Chat info={info} /> : <Navigate to="/login" />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </main>
      <footer>This is a research aid, not legal advice. · Data: CourtListener (Free Law Project), public domain.</footer>
    </>
  );
}

createRoot(document.getElementById("root")).render(
  <StrictMode><BrowserRouter basename="/app"><App /></BrowserRouter></StrictMode>
);
