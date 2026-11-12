// Start of the React app: asks the server who is logged in, then shows the right page.
// The server checks the login and the role again on every /api call: this is only for display.
import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { api, me } from "./api.js";
import Abstentions from "./admin/Abstentions.jsx";
import AdminLayout from "./admin/AdminLayout.jsx";
import Analytics from "./admin/Analytics.jsx";
import Compare from "./admin/Compare.jsx";
import Corpus from "./admin/Corpus.jsx";
import Eval from "./admin/Eval.jsx";
import Messages from "./admin/Messages.jsx";
import EvalRun from "./admin/EvalRun.jsx";
import AdminHome from "./admin/Home.jsx";
import QuestionForm from "./admin/QuestionForm.jsx";
import Questions from "./admin/Questions.jsx";
import Settings from "./admin/Settings.jsx";
import Users from "./admin/Users.jsx";
import Chat from "./pages/Chat.jsx";
import Landing from "./pages/Landing.jsx";
import Login from "./pages/Login.jsx";
import Contact from "./pages/Contact.jsx";
import Privacy from "./pages/Privacy.jsx";
import Sources from "./pages/Sources.jsx";
import Terms from "./pages/Terms.jsx";
import "./style.css";
import logoMark from "./assets/logo-seal.webp";     // the Verdicta seal, bundled into /assets by Vite

function App() {
  const [info, setInfo] = useState(null);          // answer of GET /api/me
  const path = useLocation().pathname;
  const navigate = useNavigate();
  const landing = path === "/";                    // the landing page has its own top bar
  const authPage = ["/login", "/signup", "/forgot"].includes(path);   // the account pages have their own logo

  useEffect(() => { me().then(setInfo); }, []);
  // the dark pages (landing, account pages, research page) show the "not legal advice" notice inside their own design,
  // so the light footer of index.html is hidden there (it stays on every other page: NFR10, SR7)
  useEffect(() => { document.body.classList.toggle("dark-page", landing || authPage || path === "/research"); }, [landing, authPage, path]);
  if (!info) return <p className="muted" style={{ padding: 20 }}>Loading…</p>;

  // Log out always ends in the home page, logged out. If the server refuses the first try (a stale CSRF token,
  // e.g. after logging in from another tab), a fresh token is fetched and it tries once more.
  async function logout() {
    try {
      await api("/logout", {});
    } catch {
      await me();                                  // a fresh CSRF token
      await api("/logout", {}).catch(() => {});
    }
    setInfo(await me());                           // logged out, with a new CSRF token for the next login
    navigate("/");
  }

  const user = info.user;
  return (
    <>
      {!landing && !authPage && <header>
        {/* only the logo, and "Log out" for a logged-in administrator (Yasser's decision, 2026-11-12):
            the coverage line is on the research page itself, the admin menu is in the admin sidebar */}
        <Link to="/" className="brand"><img src={logoMark} alt="" /> Verdicta</Link>
        {user && (
          <button className="logout" onClick={logout} title={`Log out ${user.email}`}>
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3" />
              <path d="M10 17l-5-5 5-5" /><path d="M5 12h11" /></svg>
            Log out
          </button>
        )}
      </header>}
      <main className={landing || authPage ? "bare" : ""}>
        <Routes>
          {/* already logged in: an administrator goes to /admin, a visitor's account to the research page */}
          <Route path="/login" element={user ? <Navigate to={user.role === "admin" ? "/admin" : "/research"} /> :
            <Login onLogin={(u) => setInfo({ ...info, user: u })} />} />
          <Route path="/signup" element={user ? <Navigate to={user.role === "admin" ? "/admin" : "/research"} /> :
            <Login mode="signup" onLogin={(u) => setInfo({ ...info, user: u })} />} />   {/* visitor accounts (SPEC 11) */}
          <Route path="/forgot" element={<Login mode="forgot" />} />   {/* an administrator resets the password */}
          <Route path="/" element={<Landing info={info} />} />  {/* the story of Verdicta, then "Try a question" */}
          <Route path="/research" element={<Chat info={info} />} />    {/* open to everyone, no account (SR33) */}
          <Route path="/privacy" element={<Privacy />} />              {/* the site's information pages (Edwin) */}
          <Route path="/terms" element={<Terms />} />
          <Route path="/sources" element={<Sources />} />
          <Route path="/contact" element={<Contact />} />
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
              <Route path="messages" element={<Messages />} />
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
