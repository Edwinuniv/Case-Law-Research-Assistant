// The account pages: /login, /signup and /forgot, one design (Yasser's decision of 2026-11-12):
// - Log in: the administrator's login, as before (SR33): the same message for every failure (SR36), CSRF,
//   POST /api/login. Show/hide password, a Caps Lock warning, "Forgot password?".
// - Sign up (SPEC 11, 2026-11-12): POST /api/signup makes a 'user' account and logs it in, then the research
//   page opens; the account keeps the visitor's question history. Only the email and a password hash are stored.
// - Continue with Google (SPEC 11, 2026-11-13): components/GoogleButton.jsx, on both forms, user accounts only.
// - Forgot password: there is no email service, so it explains that an administrator resets the password
//   from the Accounts page (FR12: db.create_user resets the password of an existing email).
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import logoMark from "../assets/logo-seal.webp";   // the Verdicta seal (Yasser, 2026-11-12)
import ClipboardAnim from "../components/ClipboardAnim.jsx";
import GoogleButton from "../components/GoogleButton.jsx";   // Sign in with Google (SPEC 11, 2026-11-13)
import "./auth.css";

function PasswordInput({ id, value, onChange, autoComplete, placeholder }) {
  const [show, setShow] = useState(false);
  const [caps, setCaps] = useState(false);
  const keys = (e) => setCaps(e.getModifierState?.("CapsLock") ?? false);
  return (
    <>
      <div className="au-pass">
        <input id={id} type={show ? "text" : "password"} autoComplete={autoComplete} required value={value}
               placeholder={placeholder} onChange={onChange} onKeyUp={keys} onKeyDown={keys} />
        <button type="button" className="au-eye" onClick={() => setShow(!show)}
                aria-label={show ? "Hide password" : "Show password"}>{show ? "Hide" : "Show"}</button>
      </div>
      {caps && <p className="au-caps" role="status">Caps Lock is on</p>}
    </>
  );
}

function LoginForm({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  async function submit(e) {
    e.preventDefault();                 // stay on the page: React sends the form itself
    setBusy(true); setError("");
    try {
      const data = await api("/login", { email, password });
      onLogin(data.user);
      navigate(data.user.role === "admin" ? "/admin" : "/research");   // an administrator, or a visitor's account
    } catch (err) {
      setError(err.message);            // "Wrong email or password." or "Too many failed logins..."
    } finally {
      setBusy(false);
      setPassword("");
    }
  }

  return (
    <form onSubmit={submit} className="au-form">
      <label htmlFor="email">Email</label>
      <input id="email" type="email" autoComplete="username" required value={email} placeholder="you@example.com"
             onChange={(e) => setEmail(e.target.value)} />
      <div className="au-row"><label htmlFor="password">Password</label><Link to="/forgot" className="au-link">Forgot password?</Link></div>
      <PasswordInput id="password" value={password} autoComplete="current-password" onChange={(e) => setPassword(e.target.value)} />
      {error && <p className="au-error" role="alert">{error}</p>}
      <button className="au-submit" disabled={busy}>{busy ? <span className="au-spin" aria-label="Checking" /> : "Log in"}</button>
      <GoogleButton mode="login" onLogin={onLogin} />
      <p className="au-switch">Don't have an account? <Link to="/signup">Sign up</Link></p>
    </form>
  );
}

function SignupForm({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const data = await api("/signup", { email, password });   // makes the account and logs it in
      onLogin(data.user);
      navigate("/research");
    } catch (err) {
      setError(err.message);            // a used email, a short password, or too many accounts from this address
      setPassword("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="au-form">
      <label htmlFor="semail">Email</label>
      <input id="semail" type="email" autoComplete="email" required value={email} placeholder="you@example.com"
             onChange={(e) => setEmail(e.target.value)} />
      <label htmlFor="spass">Password</label>
      <PasswordInput id="spass" value={password} autoComplete="new-password" placeholder="At least 10 characters"
                     onChange={(e) => setPassword(e.target.value)} />
      {error && <p className="au-error" role="alert">{error}</p>}
      <button className="au-submit" disabled={busy}>{busy ? <span className="au-spin" aria-label="Creating" /> : "Create account"}</button>
      <GoogleButton mode="signup" onLogin={onLogin} />
      <p className="au-small">We keep only your email and your questions, so you find them again. <Link to="/privacy">Privacy</Link></p>
      <p className="au-switch">Already have an account? <Link to="/login">Log in</Link></p>
    </form>
  );
}

function ForgotPanel() {
  return (
    <div className="au-form">
      <div className="au-steps">
        <div><span>1</span><p>Contact your Verdicta administrator.</p></div>
        <div><span>2</span><p>They set a new password for your email on the <b>Accounts</b> page.</p></div>
        <div><span>3</span><p>Log in with it, then keep it private.</p></div>
      </div>
      <p className="au-muted">For your security, passwords are never sent by email, and nobody can read them:
        they are stored only as a bcrypt hash.</p>
      <Link to="/login" className="au-submit au-as-button">Back to log in</Link>
    </div>
  );
}

const TEXT = {
  login: { title: "Welcome back", sub: "Log in to your Verdicta account." },
  signup: { title: "Create your account", sub: "Keep your questions and their answers, and find them again." },
  forgot: { title: "Forgot your password?", sub: "An administrator resets it for you." },
};

export default function Login({ mode = "login", onLogin }) {
  const t = TEXT[mode];
  return (
    <div className="au">
      <aside className="au-side">
        <Link to="/" className="au-brand" aria-hidden="true" tabIndex={-1}><img src={logoMark} alt="" /> Verdicta</Link>
        <Link to="/" className="au-back"><span aria-hidden="true">←</span> Back</Link>
        <ClipboardAnim />
        <div className="au-side-text">
          <p className="au-quote">Ask the Court. <em>Hear only what it said.</em></p>
          <ul>
            <li><b>0</b> false citations shown on our test questions</li>
            <li><b>6</b> checks on every sentence</li>
            <li><b>2,415</b> Supreme Court decisions, 2000 to 2024</li>
          </ul>
        </div>
      </aside>

      <section className="au-main">
        <div className="au-top-small">
          <Link to="/" className="au-brand au-brand-small"><img src={logoMark} alt="" /> Verdicta</Link>
          <Link to="/" className="au-back"><span aria-hidden="true">←</span> Back</Link>
        </div>
        <div className="au-card" key={mode}>
          {mode !== "forgot" && (
            <div className="au-tabs" role="tablist">
              <Link to="/login" role="tab" aria-selected={mode === "login"} className={mode === "login" ? "on" : ""}>Log in</Link>
              <Link to="/signup" role="tab" aria-selected={mode === "signup"} className={mode === "signup" ? "on" : ""}>Sign up</Link>
              <i className={`au-tab-bg at-${mode}`} />
            </div>
          )}
          <h1>{t.title}</h1>
          <p className="au-sub">{t.sub}</p>
          {mode === "login" && <LoginForm onLogin={onLogin} />}
          {mode === "signup" && <SignupForm onLogin={onLogin} />}
          {mode === "forgot" && <ForgotPanel />}
        </div>
        <p className="au-legal">This is a research aid, not legal advice.</p>
        <nav className="au-links" aria-label="Site information">
          <Link to="/privacy">Privacy</Link><Link to="/terms">Terms of use</Link>
          <Link to="/sources">Sources &amp; licences</Link><Link to="/contact">Contact</Link>
        </nav>
      </section>
    </div>
  );
}
