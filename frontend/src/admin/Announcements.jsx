// Announcements (Edwin, SPEC 11, 2026-11-20, from CedarPay): a short message shown as a banner on every page until it
// ends. Information (gold) or warning (red); at most 300 characters and 30 days; 3 shown at a time, newest first.
import { useState } from "react";
import { api } from "../api.js";
import { Waiting, day, useLoad } from "./useLoad.jsx";

const EMPTY = { text: "", level: "info", days: 1, starts_in_hours: 0 };

export default function Announcements() {
  const [list, error, reload] = useLoad("/admin/announcements");
  const [form, setForm] = useState(EMPTY);
  const [msg, setMsg] = useState("");
  async function post(e) {
    e.preventDefault();
    setMsg("");
    try {
      await api("/admin/announcements", { ...form, days: Number(form.days), starts_in_hours: Number(form.starts_in_hours) });
      setForm(EMPTY); setMsg("Posted. Visitors see it at their next page load."); reload();
    } catch (err) { setMsg(err.message); }
  }
  async function remove(id) {
    try { await api(`/admin/announcements/${id}/delete`, {}); reload(); } catch (err) { setMsg(err.message); }
  }
  return (
    <>
      <h2>Site <em>announcements</em></h2>
      <p className="ad-lead">A short message at the top of every page, for everyone, until it ends. Visitors can close it.</p>
      <form className="ad-card ad-form" onSubmit={post}>
        <label className="ad-field" style={{ flex: "1 1 100%" }}>Message ({300 - form.text.length} characters left)
          <textarea maxLength={300} rows={2} required value={form.text} placeholder="Maintenance tonight from 22:00 to 23:00."
                    onChange={(e) => setForm({ ...form, text: e.target.value })} /></label>
        <label className="ad-field">Kind<select value={form.level} onChange={(e) => setForm({ ...form, level: e.target.value })}>
          <option value="info">Information (gold)</option><option value="warning">Warning (red)</option></select></label>
        <label className="ad-field">Lasts (days, at most 30)<input type="number" min="0.5" max="30" step="0.5" value={form.days}
          onChange={(e) => setForm({ ...form, days: e.target.value })} /></label>
        <label className="ad-field">Starts in (hours, 0 = now)<input type="number" min="0" max="720" step="1" value={form.starts_in_hours}
          onChange={(e) => setForm({ ...form, starts_in_hours: e.target.value })} /></label>
        <button>Post the announcement</button>
        {msg && <span className="muted">{msg}</span>}
      </form>
      {!list ? <Waiting data={list} error={error} /> : (
        <div className="ad-table wide">
          <table>
            <thead><tr><th>State</th><th>Kind</th><th>Message</th><th>Starts</th><th>Ends</th><th>By</th><th></th></tr></thead>
            <tbody>
              {list.length === 0 && <tr><td colSpan={7} className="muted">No announcement yet.</td></tr>}
              {list.map((a) => (
                <tr key={a.id} className={a.state === "active" ? "hl" : ""}>
                  <td>{a.state}</td><td>{a.level === "warning" ? "warning" : "information"}</td><td>{a.text}</td>
                  <td>{day(a.starts_at)}</td><td>{day(a.ends_at)}</td><td>{a.created_by || "–"}</td>
                  <td><button className="light" onClick={() => remove(a.id)}>Delete</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
