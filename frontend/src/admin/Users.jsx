// Accounts (FR12): an administrator creates and disables the other administrators.
// Since 2026-11-14 (SPEC 11, Joe; Edwin's restyled page, changed with Joe's OK): EVERY account is listed, visitors'
// accounts too, with its details (counted like the PDF exports), a Free/Paid switch, the daily limits and the
// follow-ups switch; a click on an account opens its details (UserDetail.jsx). The list: GET /api/admin/users.
// Joe is writing frontend/src/components/PasswordRules.jsx (the password policy): it goes under the password
// field below once it lands, with the props agreed with him. Until then the server's rule (10+ characters) applies.
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { day, useLoad, Waiting } from "./useLoad.jsx";

export default function Users({ user }) {
  const [list, error] = useLoad("/admin/users");
  const [users, setUsers] = useState(null);           // the list after a change
  const [form, setForm] = useState({ email: "", password: "" });
  const [msg, setMsg] = useState("");
  const [settings, , reloadSettings] = useLoad("/admin/settings");
  const [limits, setLimits] = useState(null);         // the form's values once changed
  const [limitMsg, setLimitMsg] = useState("");
  const shown = users || list;
  if (!shown) return <Waiting data={list} error={error} />;
  const lim = limits || { free_daily_questions: settings?.free_daily_questions ?? 10,
                          paid_daily_questions: settings?.paid_daily_questions ?? 100 };

  async function setPlan(id, plan) {
    setMsg("");
    try { setUsers(await api(`/admin/users/${id}/plan`, { plan })); } catch (err) { setMsg(err.message); }
  }
  async function saveLimits(e) {
    e.preventDefault(); setLimitMsg("");
    try {
      await api("/admin/limits", { free_daily_questions: +lim.free_daily_questions, paid_daily_questions: +lim.paid_daily_questions });
      setLimitMsg("Saved."); reloadSettings();
    } catch (err) { setLimitMsg(err.message); }
  }
  async function switchFollowUps() {
    try { await api("/admin/follow-ups", { on: !settings?.follow_ups }); reloadSettings(); } catch (err) { setLimitMsg(err.message); }
  }

  async function create(e) {
    e.preventDefault(); setMsg("");
    try { setUsers(await api("/admin/users", form)); setForm({ email: "", password: "" }); setMsg("Administrator account created."); }
    catch (err) { setMsg(err.message); }
  }
  async function toggle(id) {
    try { setUsers(await api(`/admin/users/${id}/toggle`, {})); } catch (err) { setMsg(err.message); }
  }

  return (
    <>
      <h2>All <em>accounts</em></h2>
      <p className="ad-lead">{shown.length} account(s): {shown.filter((u) => u.role === "admin").length} administrator(s),
        {" "}{shown.filter((u) => u.role === "user").length} visitor account(s) ({shown.filter((u) => u.plan === "paid" && u.role === "user").length} paid),
        {" "}{shown.filter((u) => u.active).length} active. Click an account to see its questions, chats and log.</p>
      {/* PDF exports (Yasser, part 4): the server makes the file; each download is written to the admin log */}
      <p><a className="ad-pdf" href="/api/admin/users/pdf" download>Download all accounts as PDF</a></p>
      <div className="ad-table">
        <table><thead><tr><th>Email</th><th>Role</th><th>Plan</th><th>Signed up</th><th>Last login</th><th>Logins</th>
          <th>Last activity</th><th>Questions</th><th>Active</th><th>Locked until</th><th></th><th></th></tr></thead>
          <tbody>{shown.map((u) => (
            <tr key={u.id}><td><Link to={`/admin/users/${u.id}`}><b>{u.email}</b></Link></td><td>{u.role}</td>
              <td>{u.role === "user"
                ? <button className="light" style={{ whiteSpace: "nowrap" }} title="Switch the plan (no real payment)"
                          onClick={() => setPlan(u.id, u.plan === "paid" ? "free" : "paid")}>{u.plan === "paid" ? "Paid → free" : "Free → paid"}</button>
                : "–"}</td>
              <td>{day(u.created_at).slice(0, 10)}</td><td>{day(u.last_login) || "–"}</td><td>{u.logins}</td>
              <td>{day(u.last_activity) || "–"}</td><td>{u.questions}</td>
              <td>{u.active ? "✓ yes" : "✕ no"}</td><td>{u.locked_until ? day(u.locked_until).slice(11) : ""}</td>
              <td>{u.email !== user.email &&
                <button className="light" onClick={() => toggle(u.id)}>{u.active ? "Disable" : "Enable"}</button>}</td>
              <td><a className="ad-pdf small" href={`/api/admin/users/${u.id}/pdf`} download>PDF</a></td></tr>
          ))}</tbody></table>
      </div>
      <form className="ad-card" onSubmit={saveLimits}>
        <h3>Questions per day, and follow-ups</h3>
        <div className="ad-form">
          <label className="ad-field">Free plan<input type="number" min={1} max={1000} required value={lim.free_daily_questions}
                                                    onChange={(e) => setLimits({ ...lim, free_daily_questions: e.target.value })} /></label>
          <label className="ad-field">Paid plan<input type="number" min={1} max={1000} required value={lim.paid_daily_questions}
                                                    onChange={(e) => setLimits({ ...lim, paid_daily_questions: e.target.value })} /></label>
          <button>Save the limits</button>
        </div>
        <p className="muted">A day starts at midnight, Beirut time. Administrators have no limit. Visitors without an
          account get one question per browser session.</p>
        <p>Follow-up questions in saved chats: <b>{settings?.follow_ups ? "on" : "off"}</b>{" "}
          <button type="button" className="light" onClick={switchFollowUps}>{settings?.follow_ups ? "Switch off" : "Switch on"}</button></p>
        <p className="muted">Off until the follow-up measurement meets its rule (EVALUATION.md, Edwin).</p>
        {limitMsg && <p className="muted">{limitMsg}</p>}
      </form>
      <form className="ad-card" onSubmit={create}>
        <h3>Create an administrator account</h3>
        <div className="ad-form">
          <label className="ad-field">Email<input type="email" required value={form.email}
                                                 onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
          <label className="ad-field">Password (10+ characters)<input type="password" minLength={10} required value={form.password}
                                                                     onChange={(e) => setForm({ ...form, password: e.target.value })} /></label>
          <button>Create</button>
        </div>
        {msg && <p className="muted">{msg}</p>}
        <p className="muted">Give the new administrator their email and password yourself.</p>
      </form>
    </>
  );
}
