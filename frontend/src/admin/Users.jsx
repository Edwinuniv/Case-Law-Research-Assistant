// Accounts (FR12): an administrator creates and disables the other administrators.
// Visitors need no account (SR33), so there is no role to choose. The list comes from GET /api/admin/users.
// Joe is writing frontend/src/components/PasswordRules.jsx (the password policy): it goes under the password
// field below once it lands, with the props agreed with him. Until then the server's rule (10+ characters) applies.
import { useState } from "react";
import { api } from "../api.js";
import { day, useLoad, Waiting } from "./useLoad.jsx";

export default function Users({ user }) {
  const [list, error] = useLoad("/admin/users");
  const [users, setUsers] = useState(null);           // the list after a change
  const [form, setForm] = useState({ email: "", password: "" });
  const [msg, setMsg] = useState("");
  const shown = users || list;
  if (!shown) return <Waiting data={list} error={error} />;

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
      <h2>Administrator <em>accounts</em></h2>
      <p className="ad-lead">{shown.length} account(s), {shown.filter((u) => u.active).length} active. Visitors use the research page
        without an account; there is no sign-up page.</p>
      {/* PDF exports (Yasser, part 4): the server makes the file; each download is written to the admin log */}
      <p><a className="ad-pdf" href="/api/admin/users/pdf" download>Download all accounts as PDF</a></p>
      <div className="ad-table">
        <table><thead><tr><th>Email</th><th>Role</th><th>Active</th><th>Locked until</th><th>Created</th><th></th><th></th></tr></thead>
          <tbody>{shown.map((u) => (
            <tr key={u.id}><td><b>{u.email}</b></td><td>{u.role}</td><td>{u.active ? "✓ yes" : "✕ no"}</td>
              <td>{u.locked_until ? day(u.locked_until).slice(11) : ""}</td><td>{day(u.created_at).slice(0, 10)}</td>
              <td>{u.email !== user.email &&
                <button className="light" onClick={() => toggle(u.id)}>{u.active ? "Disable" : "Enable"}</button>}</td>
              <td><a className="ad-pdf small" href={`/api/admin/users/${u.id}/pdf`} download>PDF</a></td></tr>
          ))}</tbody></table>
      </div>
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
