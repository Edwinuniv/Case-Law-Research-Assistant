// Start of the React app: asks the server who is logged in, then shows the right page.
// The server checks the login and the role again on every /api call: this is only for display.
import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, Navigate, Route, Routes } from "react-router-dom";
import { api, me } from "./api.js";
import Abstentions from "./admin/Abstentions.jsx";
import AdminLayout from "./admin/AdminLayout.jsx";
import Analytics from "./admin/Analytics.jsx";
import Compare from "./admin/Compare.jsx";
import Corpus from "./admin/Corpus.jsx";
import Eval from "./admin/Eval.jsx";
import EvalRun from "./admin/EvalRun.jsx";
import AdminHome from "./admin/Home.jsx";
import QuestionForm from "./admin/QuestionForm.jsx";
import Questions from "./admin/Questions.jsx";
import Settings from "./admin/Settings.jsx";
import Users from "./admin/Users.jsx";
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
        <Link to="/">Research</Link>
        {user && <span>{user.email}</span>}
        {user?.role === "admin" && <Link to="/admin">Admin</Link>}
        {user ? <button className="link" onClick={logout}>Log out</button>
              : <Link to="/login">Admin login</Link>}      {/* only the administrator logs in */}
      </header>
      <main>
        <Routes>
          <Route path="/login" element={user ? <Navigate to="/admin" /> :
            <Login onLogin={(u) => setInfo({ ...info, user: u })} />} />
          <Route path="/" element={<Chat info={info} />} />    {/* open to everyone, no account (SR33) */}
          {user?.role === "admin" && (       // display only: the server refuses /admin and /api/admin to others
            <Route path="/admin" element={<AdminLayout user={user} />}>
              <Route index element={<AdminHome />} />
              <Route path="settings" element={<Settings />} />
              <Route path="eval" element={<Eval />} />
              <Route path="eval/compare" element={<Compare />} />
              <Route path="eval/:runId" element={<EvalRun />} />
              <Route path="questions" element={<Questions />} />
              <Route path="questions/edit" element={<QuestionForm user={user} />} />
              <Route path="abstentions" element={<Abstentions />} />
              <Route path="analytics" element={<Analytics />} />
              <Route path="corpus" element={<Corpus />} />
              <Route path="users" element={<Users user={user} />} />
            </Route>
          )}
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </main>
    </>
  );
}

createRoot(document.getElementById("root")).render(
  <StrictMode><BrowserRouter><App /></BrowserRouter></StrictMode>
);
