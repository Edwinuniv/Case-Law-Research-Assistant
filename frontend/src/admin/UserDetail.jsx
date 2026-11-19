// One account's details (SPEC 11, 2026-11-14, Joe; Dr. Salloum's request 4): its details, its questions, its chats
// and its log, from GET /api/admin/users/{id}. Opening this page is written to the admin log (reading someone's data).
// The log of a visitor's account is the user log (Yasser); for an administrator, what that administrator did.
import { Link, useParams } from "react-router-dom";
import { day, useLoad, Waiting } from "./useLoad.jsx";

function detail(d) {                                  // the log's small JSON detail, readable
  return Object.entries(d || {}).map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`).join(" · ");
}

export default function UserDetail() {
  const { id } = useParams();
  const [d, error] = useLoad(`/admin/users/${id}`);
  if (!d) return <Waiting data={d} error={error} />;
  const u = d.user;
  const facts = [["Role", u.role], ["Plan", u.role === "user" ? u.plan : "–"], ["Active", u.active ? "yes" : "no"],
    ["Signed up", day(u.created_at)], ["Last login", day(u.last_login) || "–"], ["Number of logins", u.logins],
    ["Last activity", day(u.last_activity) || "–"], ["Questions asked", u.questions], ["Chats", d.chats.length]];

  return (
    <>
      <p><Link to="/admin/users">← All accounts</Link></p>
      <h2>{u.email}</h2>
      <p><a className="ad-pdf" href={`/api/admin/users/${u.id}/pdf`} download>Download this account as PDF</a>{" "}
        <a className="ad-pdf" href={`/api/admin/users/${u.id}/log?format=csv`} download>Log as CSV</a></p>
      <div className="ad-table">
        <table><tbody>{facts.map(([k, v]) => <tr key={k}><th>{k}</th><td>{v}</td></tr>)}</tbody></table>
      </div>

      <h3>Questions ({d.questions.length})</h3>
      {d.questions.length === 0 ? <p className="muted">No question yet.</p> : (
        <div className="ad-table">
          <table><thead><tr><th>Date</th><th>Status</th><th>Question</th><th>Chat</th></tr></thead>
            <tbody>{d.questions.map((q) => (
              <tr key={q.id}><td>{day(q.created_at)}</td><td>{q.status}</td><td>{q.question}</td><td>{q.chat_id ?? ""}</td></tr>
            ))}</tbody></table>
        </div>
      )}

      <h3>Chats ({d.chats.length})</h3>
      {d.chats.length === 0 ? <p className="muted">No saved chat.</p> : (
        <div className="ad-table">
          <table><thead><tr><th>Chat</th><th>Title</th><th>Questions</th><th>Last question</th></tr></thead>
            <tbody>{d.chats.map((c) => (
              <tr key={c.id}><td>{c.id}</td><td>{c.title}</td><td>{c.questions}</td><td>{day(c.updated_at)}</td></tr>
            ))}</tbody></table>
        </div>
      )}

      <h3>Log ({d.log.length})</h3>
      {d.log.length === 0 ? <p className="muted">Nothing recorded yet.</p> : (
        <div className="ad-table">
          <table><thead><tr><th>Date</th><th>Event</th><th>Detail</th></tr></thead>
            <tbody>{d.log.map((row) => (
              <tr key={row.id}><td>{day(row.at)}</td><td>{row.event || row.action}</td>
                <td className="muted">{detail(row.detail)}{row.status ? ` · HTTP ${row.status}` : ""}</td></tr>
            ))}</tbody></table>
        </div>
      )}
    </>
  );
}
