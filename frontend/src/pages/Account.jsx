// My account (Edwin, SPEC 11, 2026-11-20, from CedarPay's profile): the account's details, its plan, change password,
// delete the account. For a logged-in 'user' account; the server checks it again on every call (/api/account).
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import SitePage from "./SitePage.jsx";

function ChangePassword() {
  const [form, setForm] = useState({ current: "", new: "" });
  const [state, setState] = useState({ busy: false, ok: "", error: "" });
  async function submit(e) {
    e.preventDefault();
    setState({ busy: true, ok: "", error: "" });
    try {
      await api("/account/password", form);
      setState({ busy: false, ok: "Your password was changed. We sent you a notice by email.", error: "" });
      setForm({ current: "", new: "" });
    } catch (err) {
      setState({ busy: false, ok: "", error: err.message });    // a wrong current password counts toward the lock
    }
  }
  return (
    <form className="sp-form" onSubmit={submit}>
      <label>Current password<input type="password" autoComplete="current-password" required value={form.current}
        onChange={(e) => setForm({ ...form, current: e.target.value })} /></label>
      <label>New password (10 characters at least)<input type="password" autoComplete="new-password" required minLength={10}
        value={form.new} onChange={(e) => setForm({ ...form, new: e.target.value })} /></label>
      {state.error && <p className="sp-err" role="alert">{state.error}</p>}
      {state.ok && <p className="sp-ok" role="status">{state.ok}</p>}
      <button disabled={state.busy}>Change my password</button>
    </form>
  );
}

function DeleteAccount({ google, email, onDeleted }) {
  const [confirm, setConfirm] = useState("");
  const [sure, setSure] = useState(false);
  const [error, setError] = useState("");
  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      await api("/account/delete", google ? { email: confirm } : { password: confirm });
      await onDeleted();
    } catch (err) {
      setError(err.message);
    }
  }
  return (
    <form className="sp-form ac-danger" onSubmit={submit}>
      <p>This deletes your account, your questions and their answers, your chats and your ratings, at once and for
        good. A paid plan's test subscription is cancelled. We send you one last email.</p>
      <label>{google ? <>Type your email address (<b>{email}</b>) to confirm</> : "Your password, to confirm"}
        <input type={google ? "email" : "password"} autoComplete={google ? "off" : "current-password"} required
               value={confirm} onChange={(e) => setConfirm(e.target.value)} /></label>
      <label className="ac-check"><input type="checkbox" checked={sure} onChange={(e) => setSure(e.target.checked)} />
        I understand that this cannot be undone.</label>
      {error && <p className="sp-err" role="alert">{error}</p>}
      <button className="ac-delete" disabled={!sure || !confirm}>Delete my account</button>
    </form>
  );
}

export default function Account({ onDeleted }) {
  const [a, setA] = useState(null);
  const [error, setError] = useState("");
  const navigate = useNavigate();
  useEffect(() => { api("/account").then(setA, (e) => setError(e.message)); }, []);
  async function deleted() {
    navigate("/");                                             // home first: /account would send to /login
    await onDeleted();                                         // then the page learns nobody is logged in
  }
  return (
    <SitePage kicker="Your account" title="My" accent="account">
      {error && <p className="sp-err" role="alert">{error}</p>}
      {a && (
        <>
          <h2>Your details</h2>
          <div className="sp-card ac-details">
            <p><span>Email</span><b>{a.email}</b></p>
            <p><span>Email verified</span><b>{a.email_verified ? "Yes" : <>Not yet · <Link to="/verify">enter the code</Link></>}</b></p>
            <p><span>Sign in with</span><b>{a.google ? "Google" : "Email and password"}</b></p>
            <p><span>Member since</span><b>{a.created_at.slice(0, 10)}</b></p>
            <p><span>Plan</span><b>{a.plan.plan === "paid" ? "Paid" : "Free"} · {a.plan.left_today} of {a.plan.daily_limit}
              {" "}questions left today · <Link to="/pricing">Plans</Link></b></p>
          </div>
          <h2>Password</h2>
          {a.google
            ? <p>You sign in with Google, so your account has no password you know. To set one, use{" "}
                <Link to="/forgot">Forgot password?</Link> with {a.email}.</p>
            : <ChangePassword />}
          <h2>Delete my account</h2>
          <DeleteAccount google={a.google} email={a.email} onDeleted={deleted} />
        </>
      )}
    </SitePage>
  );
}
