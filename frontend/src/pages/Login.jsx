// Login page for the administrator only (SR33): visitors use the research page without an account.
// Accounts are created by an administrator (FR12): there is no "sign up" link. The server gives the same message for every failure.
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api.js";

export default function Login({ onLogin }) {
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
      navigate("/admin");
    } catch (err) {
      setError(err.message);            // "Wrong email or password." or "Too many failed logins..."
    } finally {
      setBusy(false);
      setPassword("");
    }
  }

  return (
    <form className="card login" onSubmit={submit}>
      <h2 style={{ marginTop: 0 }}>Administrator login</h2>
      <label htmlFor="email">Email</label>
      <input id="email" type="email" autoComplete="username" required value={email}
             onChange={(e) => setEmail(e.target.value)} />
      <label htmlFor="password">Password</label>
      <input id="password" type="password" autoComplete="current-password" required value={password}
             onChange={(e) => setPassword(e.target.value)} />
      {error && <p className="error" role="alert">{error}</p>}
      <p><button disabled={busy}>{busy ? "Checking…" : "Log in"}</button></p>
      <p className="muted">Only administrators log in. The <Link to="/">research page</Link> needs no account.</p>
    </form>
  );
}
