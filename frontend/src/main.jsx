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
import Previews from "./admin/Previews.jsx";                // page previews (Edwin, SPEC 11, 2026-11-20)
import Users from "./admin/Users.jsx";
import UserDetail from "./admin/UserDetail.jsx";
import AllQuestions from "./admin/AllQuestions.jsx";
import AdminLog from "./admin/AdminLog.jsx";
import Feedback from "./admin/Feedback.jsx";                // answer feedback (Edwin, SPEC 11, 2026-11-20)
import Chat from "./pages/Chat.jsx";
import Landing from "./pages/Landing.jsx";
import Login from "./pages/Login.jsx";
import Contact from "./pages/Contact.jsx";
import Pricing from "./pages/Pricing.jsx";
import Account from "./pages/Account.jsx";                 // my account (Edwin, SPEC 11, 2026-11-20)
import Privacy from "./pages/Privacy.jsx";
import Sources from "./pages/Sources.jsx";
import Terms from "./pages/Terms.jsx";
import ErrorPage, { ErrorBoundary } from "./components/ErrorPage.jsx";   // error pages that reveal nothing (Edwin)
import "./style.css";
import "./life.css";                              // white light on the dark pages (Edwin; for Yasser's opinion)
import "./theme.css";                             // dark pages with white sections, or the reverse (Edwin)
import Logo from "./components/Logo.jsx";        // the Verdicta logo, white or black V for the theme (Edwin, 2026-11-19)
import ThemeSwitch from "./components/ThemeSwitch.jsx";
import Tour from "./components/Tour.jsx";
import AnnouncementsBar from "./components/Announcements.jsx";   // banners for everyone (Edwin, 2026-11-20)
import AdminAnnouncements from "./admin/Announcements.jsx";                  // the guided tour of the research page (Edwin, 2026-11-20)   // Settings: the appearance (Edwin, 2026-11-19)

// The loading screen of index.html (Edwin, 2026-11-19): it fades out once the page is ready. On the first visit
// of this tab it stays until its animation has played once (about 2.1 s since the page started loading).
function hideSplash() {
  const el = document.getElementById("splash");
  if (!el) return;
  let first = true;
  try { first = !sessionStorage.getItem("splash-seen"); sessionStorage.setItem("splash-seen", "1"); } catch { /* private mode */ }
  setTimeout(() => {
    el.classList.add("out");
    setTimeout(() => el.remove(), 600);
  }, first ? Math.max(0, 2100 - performance.now()) : 0);
}

function App() {
  const [info, setInfo] = useState(null);          // answer of GET /api/me
  const path = useLocation().pathname;
  const navigate = useNavigate();
  const landing = path === "/";                    // the landing page has its own top bar
  const authPage = ["/login", "/signup", "/forgot", "/reset", "/verify"].includes(path);   // the account pages have their own logo

  useEffect(() => {
    me().then(setInfo, () => setInfo({ failed: true }))   // no answer from the server: say so, not "Loading…" forever
      .finally(hideSplash);
  }, []);
  // the dark pages (landing, account pages, research page) show the "not legal advice" notice inside their own design,
  // so the light footer of index.html is hidden there (it stays on every other page: NFR10, SR7)
  useEffect(() => { document.body.classList.toggle("dark-page", landing || authPage || path === "/research"); }, [landing, authPage, path]);
  if (!info) return null;                          // the loading screen of index.html is still shown
  if (info.failed) return <ErrorPage kind="offline" />;

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
      <AnnouncementsBar />
      {!landing && !authPage && <header>
        {/* only the logo, and "Log out" for a logged-in administrator (Yasser's decision, 2026-11-12):
            the coverage line is on the research page itself, the admin menu is in the admin sidebar */}
        <Link to="/" className="brand"><Logo /> Verdicta</Link>
        {user && (
          <span className="hdr-right">
          {user.role === "user" && <Link to="/account" className="hdr-account">My account</Link>}
          <button className="logout" onClick={logout} title={`Log out ${user.email}`}>
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3" />
              <path d="M10 17l-5-5 5-5" /><path d="M5 12h11" /></svg>
            Log out
          </button>
          </span>
        )}
      </header>}
      <main className={landing || authPage ? "bare" : ""}>
        <Routes>
          {/* already logged in: an administrator goes to /admin, a visitor's account to the research page */}
          <Route path="/login" element={user ? <Navigate to={user.role === "admin" ? "/admin" : "/research"} /> :
            <Login onLogin={(u) => setInfo({ ...info, user: u })} />} />
          <Route path="/signup" element={user ? <Navigate to={user.role === "admin" ? "/admin" :
                                                   info.email_verified === false ? "/verify" : "/research"} /> :
            <Login mode="signup" onLogin={(u, verify) => setInfo({ ...info, user: u,   // a code was emailed: /verify
                                                                   email_verified: verify ? false : info.email_verified })} />} />   {/* visitor accounts (SPEC 11) */}
          <Route path="/forgot" element={<Login mode="forgot" />} />   {/* a link by email (Edwin, SPEC 11) */}
          <Route path="/reset" element={<Login mode="reset" />} />     {/* the page the emailed link opens */}
          <Route path="/verify" element={!user ? <Navigate to="/login" /> : info.email_verified ? <Navigate to="/research" /> :
            <Login mode="verify" email={user.email} onVerified={async () => setInfo(await me())} />} />   {/* SPEC 11, 2026-11-20 */}
          <Route path="/" element={<Landing info={info} />} />  {/* the story of Verdicta, then "Try a question" */}
          <Route path="/research" element={<Chat info={info} />} />    {/* open to everyone, no account (SR33) */}
          <Route path="/privacy" element={<Privacy />} />              {/* the site's information pages (Edwin) */}
          <Route path="/terms" element={<Terms />} />
          <Route path="/sources" element={<Sources />} />
          <Route path="/contact" element={<Contact />} />
          <Route path="/pricing" element={<Pricing />} />
          <Route path="/account" element={!user ? <Navigate to="/login" /> : user.role === "admin" ? <Navigate to="/admin" /> :
            <Account onDeleted={async () => setInfo(await me())} />} />            {/* Free or Paid, Stripe test mode (Edwin) */}
          {user?.role === "admin" && (       // display only: the server refuses /admin and /api/admin to others
            <Route path="/admin" element={<AdminLayout user={user} />}>
              <Route index element={<AdminHome />} />
              <Route path="settings" element={<Settings />} />
              <Route path="previews" element={<Previews />} />
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
              <Route path="users/:id" element={<UserDetail />} />   {/* one account (SPEC 11, 2026-11-14) */}
              <Route path="all-questions" element={<AllQuestions />} />   {/* every question (SPEC 11, 2026-11-14) */}
              <Route path="log" element={<AdminLog />} />
              <Route path="feedback" element={<Feedback />} />
              <Route path="announcements" element={<AdminAnnouncements />} />
            </Route>
          )}
          <Route path="*" element={<ErrorPage kind="notFound" inApp />} />   {/* not a silent jump to the home page */}
        </Routes>
      </main>
      <ThemeSwitch />   {/* Settings, on every page */}
      {path === "/research" && <Tour />}
    </>
  );
}

createRoot(document.getElementById("root")).render(
  <StrictMode><ErrorBoundary><BrowserRouter><App /></BrowserRouter></ErrorBoundary></StrictMode>
);
