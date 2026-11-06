// Accounts (FR12): only an administrator creates accounts (role user or admin) and disables them.
import { useState } from "react";
import { api } from "../api.js";
import { day, useLoad, Waiting } from "./useLoad.jsx";

export default function Users({ user }) {
  const [list, error] = useLoad("/admin/users");
  const [users, setUsers] = useState(null);           // the list after a change
  const [form, setForm] = useState({ email: "", password: "", role: "user" });
  const [msg, setMsg] = useState("");
  const shown = users || list;
  if (!shown) return <Waiting data={list} error={error} />;

  async function create(e) {
    e.preventDefault(); setMsg("");
    try { setUsers(await api("/admin/users", form)); setForm({ email: "", password: "", role: "user" }); setMsg("Account created."); }
    catch (err) { setMsg(err.message); }
  }
  async function toggle(id) {
    try { setUsers(await api(`/admin/users/${id}/toggle`, {})); } catch (err) { setMsg(err.message); }
  }

  return (
    <>
      <h2>Accounts</h2>
      <table><thead><tr><th>Email</th><th>Role</th><th>Active</th><th>Locked until</th><th>Created</th><th></th></tr></thead>
        <tbody>{shown.map((u) => (
          <tr key={u.id}><td>{u.email}</td><td>{u.role}</td><td>{u.active ? "yes" : "no"}</td>
            <td>{u.locked_until ? day(u.locked_until).slice(11) : ""}</td><td>{day(u.created_at).slice(0, 10)}</td>
            <td>{u.email !== user.email &&
              <button className="light" onClick={() => toggle(u.id)}>{u.active ? "Disable" : "Enable"}</button>}</td></tr>
        ))}</tbody></table>
      <form className="card" onSubmit={create} style={{ marginTop: 14 }}>
        <b>Create an account</b><br />
        Email <input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />{" "}
        Password (10+ characters) <input type="password" minLength={10} required value={form.password}
                                         onChange={(e) => setForm({ ...form, password: e.target.value })} />{" "}
        Role <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
          <option value="user">user (research page only)</option><option value="admin">admin</option></select>{" "}
        <button>Create</button> {msg && <span className="muted">{msg}</span>}
        <p className="muted">There is no sign-up page: give the person their email and password yourself.</p>
      </form>
    </>
  );
}
