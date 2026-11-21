// The account pages: /login, /signup and /forgot, one design (Yasser's decision of 2026-11-12):
// - Log in: the administrator's login, as before (SR33): the same message for every failure (SR36), CSRF,
//   POST /api/login. Show/hide password, a Caps Lock warning, "Forgot password?".
// - Sign up (SPEC 11, 2026-11-12): POST /api/signup makes a 'user' account and logs it in, then the research
//   page opens; the account keeps the visitor's question history. Only the email and a password hash are stored.
// - Continue with Google (SPEC 11, 2026-11-13): components/GoogleButton.jsx, on both forms, user accounts only.
// - Forgot password (Edwin, SPEC 11, 2026-11-19): POST /api/password/forgot emails a link to /reset; the page
//   shows the same message for every email, so nobody learns who has an account. Administrators are still
//   reset by another administrator (Accounts page, FR12).
// - Verify (/verify, Edwin, SPEC 11, 2026-11-20): the 6-digit code emailed at sign-up; "send a new code" waits a
//   minute; "later" goes to the chat (an unverified account may ask one question).
// - Reset (/reset?token=...): the token is taken out of the address bar at once and no Referer is sent;
//   POST /api/password/reset sets the new password.
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import Logo from "../components/Logo.jsx";   // the Verdicta logo for the theme (Edwin, 2026-11-19; was the seal)
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
      onLogin(data.user, data.verify);                          // the page then opens /verify (a code was emailed)
      navigate(data.verify ? "/verify" : "/research");          // (SPEC 11, 2026-11-20)
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

function ForgotForm() {
  const [email, setEmail] = useState("");
  const [done, setDone] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      setDone((await api("/password/forgot", { email })).message);   // the same message for every email
    } catch (err) {
      setError(err.message);            // too many requests from this address
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <div className="au-form">
        <div className="au-sent" role="status"><span aria-hidden="true">✓</span><p>{done}</p></div>
        <p className="au-muted">Administrator accounts are not reset by email: another administrator sets a new
          password on the Accounts page.</p>
        <Link to="/login" className="au-submit au-as-button">Back to log in</Link>
      </div>
    );
  }
  return (
    <form onSubmit={submit} className="au-form">
      <label htmlFor="femail">Email</label>
      <input id="femail" type="email" autoComplete="email" required value={email} placeholder="you@example.com"
             onChange={(e) => setEmail(e.target.value)} />
      {error && <p className="au-error" role="alert">{error}</p>}
      <button className="au-submit" disabled={busy}>{busy ? <span className="au-spin" aria-label="Sending" /> : "Send me a link"}</button>
      <p className="au-switch">Remembered it? <Link to="/login">Log in</Link></p>
    </form>
  );
}

function ResetForm() {
  const [token] = useState(() => new URLSearchParams(window.location.search).get("token") || "");
  const [password, setPassword] = useState("");
  const [again, setAgain] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    window.history.replaceState(null, "", "/reset");          // the token leaves the address bar and the history
    const meta = document.createElement("meta");              // and no page sends it on as a Referer
    meta.name = "referrer"; meta.content = "no-referrer";
    document.head.appendChild(meta);
    return () => meta.remove();
  }, []);

  async function submit(e) {
    e.preventDefault();
    if (password !== again) { setError("The two passwords are not the same."); return; }
    setBusy(true); setError("");
    try {
      await api("/password/reset", { token, password });
      setDone(true);
    } catch (err) {
      setError(err.message);            // a short password, or "This link is not valid any more..."
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <div className="au-form">
        <div className="au-sent" role="status"><span aria-hidden="true">✓</span><p>Your password has been changed.
          You can log in with it now.</p></div>
        <Link to="/login" className="au-submit au-as-button">Log in</Link>
      </div>
    );
  }
  if (!token) {
    return (
      <div className="au-form">
        <p className="au-error" role="alert">This link is not valid any more. Ask for a new one.</p>
        <Link to="/forgot" className="au-submit au-as-button">Ask for a new link</Link>
      </div>
    );
  }
  return (
    <form onSubmit={submit} className="au-form">
      <label htmlFor="npass">New password</label>
      <PasswordInput id="npass" value={password} autoComplete="new-password" placeholder="At least 10 characters"
                     onChange={(e) => setPassword(e.target.value)} />
      <label htmlFor="npass2">The same password again</label>
      <PasswordInput id="npass2" value={again} autoComplete="new-password" onChange={(e) => setAgain(e.target.value)} />
      {error && <p className="au-error" role="alert">{error}</p>}
      {error.startsWith("This link") && <Link to="/forgot" className="au-link">Ask for a new link</Link>}
      <button className="au-submit" disabled={busy}>{busy ? <span className="au-spin" aria-label="Saving" /> : "Save the new password"}</button>
    </form>
  );
}

function VerifyForm({ email, onVerified }) {
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [wait, setWait] = useState(60);                       // the code was just sent at sign-up
  const navigate = useNavigate();

  useEffect(() => {
    if (wait <= 0) return;
    const t = setTimeout(() => setWait(wait - 1), 1000);
    return () => clearTimeout(t);
  }, [wait]);

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setError(""); setNote("");
    try {
      await api("/verify/check", { code });
      await onVerified();                                      // the page learns the account is verified
      navigate("/research");
    } catch (err) {
      setError(err.message);                                   // wrong (tries left), expired, or too many tries
      setCode("");
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    setError(""); setNote("");
    try {
      await api("/verify/send", {});
      setNote("A new code is on its way. The old one no longer works.");
      setWait(60);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <form onSubmit={submit} className="au-form">
      <p className="au-muted">We sent a 6-digit code to <b>{email}</b>. Check your spam folder too.</p>
      <label htmlFor="vcode">Code</label>
      <input id="vcode" className="au-code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}"
             maxLength={6} required value={code} placeholder="000000" autoFocus
             onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} />
      {error && <p className="au-error" role="alert">{error}</p>}
      {note && <p className="au-note" role="status">{note}</p>}
      <button className="au-submit" disabled={busy || code.length !== 6}>
        {busy ? <span className="au-spin" aria-label="Checking" /> : "Verify my email"}</button>
      <p className="au-switch">
        {wait > 0 ? <>New code in {wait} s</> : <button type="button" className="au-linkbtn" onClick={resend}>Send a new code</button>}
        {" · "}<Link to="/research">Later</Link>
      </p>
    </form>
  );
}

const TEXT = {
  login: { title: "Welcome back", sub: "Log in to your Verdicta account." },
  signup: { title: "Create your account", sub: "Keep your questions and their answers, and find them again." },
  forgot: { title: "Forgot your password?", sub: "Give your email and we send you a link to choose a new one." },
  reset: { title: "Choose a new password", sub: "Then log in with it. The link works once, for 30 minutes." },
  verify: { title: "Check your email", sub: "One last step: confirm that this address is yours." },
};

export default function Login({ mode = "login", onLogin, email, onVerified }) {
  const t = TEXT[mode];
  return (
    <div className="au">
      <aside className="au-side">
        <Link to="/" className="au-brand" aria-hidden="true" tabIndex={-1}><Logo /> Verdicta</Link>
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
          <Link to="/" className="au-brand au-brand-small"><Logo /> Verdicta</Link>
          <Link to="/" className="au-back"><span aria-hidden="true">←</span> Back</Link>
        </div>
        <div className="au-card" key={mode}>
          {(mode === "login" || mode === "signup") && (
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
          {mode === "forgot" && <ForgotForm />}
          {mode === "reset" && <ResetForm />}
          {mode === "verify" && <VerifyForm email={email} onVerified={onVerified} />}
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
