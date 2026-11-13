// Every question asked on the site (SPEC 11, 2026-11-14, Joe; Dr. Salloum's request 3): visitors, accounts and
// administrators, newest first, 100 per page, from GET /api/admin/all-questions. Filters: status, who, text.
// "Show" reads one question's answer as it was shown (GET /api/admin/all-questions/{id}).
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api.js";
import { StatusBadge } from "./charts.jsx";
import { day, useLoad, Waiting } from "./useLoad.jsx";

const STATUSES = ["", "ANSWERED", "LOW_CONFIDENCE", "NOT_SUPPORTED", "ERROR", "WELCOME"];

export default function AllQuestions() {
  const [p, setP] = useSearchParams();
  const filters = { status: p.get("status") || "", who: p.get("who") || "", q: p.get("q") || "", page: p.get("page") || "1" };
  const [d, error] = useLoad(`/admin/all-questions?${new URLSearchParams(filters)}`);
  const [text, setText] = useState(filters.q);
  const [open, setOpen] = useState({});            // id -> the question with its answer as shown
  const set = (k, v) => setP({ ...filters, [k]: v, page: k === "page" ? v : "1" });

  async function show(id) {
    if (open[id]) { setOpen({ ...open, [id]: null }); return; }
    try { setOpen({ ...open, [id]: await api(`/admin/all-questions/${id}`) }); } catch (e) { setOpen({ ...open, [id]: { error: e.message } }); }
  }

  const pages = d ? Math.max(1, Math.ceil(d.total / d.per_page)) : 1;
  return (
    <>
      <h2>All <em>questions</em></h2>
      <p className="ad-lead">Every question asked on the site, by visitors, accounts and administrators: what people ask,
        to improve the site and the answers.</p>
      <form className="ad-card ad-form" onSubmit={(e) => { e.preventDefault(); set("q", text); }}>
        <label className="ad-field">Status<select value={filters.status} onChange={(e) => set("status", e.target.value)}>
          {STATUSES.map((s) => <option key={s} value={s}>{s ? s.replace("_", " ").toLowerCase() : "all"}</option>)}</select></label>
        <label className="ad-field">Who<select value={filters.who === "visitors" ? "visitors" : filters.who ? "one" : ""}
                                              onChange={(e) => set("who", e.target.value === "visitors" ? "visitors" : "")}>
          <option value="">everyone</option><option value="visitors">visitors without an account</option>
          {filters.who && filters.who !== "visitors" && <option value="one">account {filters.who}</option>}</select></label>
        <label className="ad-field">Text<input value={text} onChange={(e) => setText(e.target.value)} placeholder="e.g. Chevron" /></label>
        <button>Search</button>
      </form>
      {!d ? <Waiting data={d} error={error} /> : (
        <>
          <p className="muted">{d.total} question(s) · page {d.page} of {pages}</p>
          <div className="ad-table">
            <table><thead><tr><th>Date</th><th>Status</th><th>Question</th><th>Who</th><th>Chat</th><th></th></tr></thead>
              <tbody>{d.rows.map((q) => [
                <tr key={q.id}><td>{day(q.created_at)}</td><td><StatusBadge status={q.status} /></td><td>{q.question}</td>
                  <td>{q.email ? <Link to={`/admin/users/${q.user_id}`}>{q.email}</Link> : <span className="muted">visitor</span>}</td>
                  <td>{q.chat_id ?? ""}</td>
                  <td><button className="light" onClick={() => show(q.id)}>{open[q.id] ? "Hide" : "Show"}</button></td></tr>,
                open[q.id] && (
                  <tr key={`${q.id}-a`}><td colSpan={6}>
                    {open[q.id].error ? <p className="error">{open[q.id].error}</p> : <>
                      <p className="muted">{open[q.id].reason}</p>
                      {(open[q.id].shown?.sentences || []).map((s, i) => (
                        <p key={i}>{s.text} <span className="muted">{s.citations.map((c) => c.label).join("; ")}</span></p>))}
                      {!open[q.id].shown && <p className="muted">The answer as shown was not saved for this question.</p>}
                      {open[q.id].shown && !(open[q.id].shown.sentences || []).length && <p className="muted">No sentence was shown.</p>}
                    </>}
                  </td></tr>),
              ])}</tbody></table>
          </div>
          <div className="ad-form" style={{ marginTop: 12 }}>
            <button className="light" disabled={d.page <= 1} onClick={() => set("page", String(d.page - 1))}>← Newer</button>
            <button className="light" disabled={d.page >= pages} onClick={() => set("page", String(d.page + 1))}>Older →</button>
          </div>
        </>
      )}
    </>
  );
}
