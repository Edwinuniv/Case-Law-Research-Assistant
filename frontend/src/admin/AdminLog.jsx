// The admin log (SPEC 11, 2026-11-13, Yasser's table; this page Joe, 2026-11-14): everything the administrators did,
// newest first, from GET /api/admin/log, with the CSV download. A failed login ON an administrator's account is shown
// as an attempt, made by whoever typed that email (SPEC 11).
import { Link } from "react-router-dom";
import { day, useLoad, Waiting } from "./useLoad.jsx";

const detail = (d) => Object.entries(d || {}).map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`).join(" · ");

export default function AdminLog() {
  const [rows, error] = useLoad("/admin/log");
  if (!rows) return <Waiting data={rows} error={error} />;
  return (
    <>
      <h2>Admin <em>log</em></h2>
      <p className="ad-lead">Everything the administrators did: logins, every change, every export. Rows are never edited.</p>
      <p><a className="ad-pdf" href="/api/admin/log?format=csv" download>Download as CSV</a></p>
      <p className="muted">{rows.length} row(s){rows.length === 500 ? " (the latest 500)" : ""}</p>
      <div className="ad-table">
        <table><thead><tr><th>Date</th><th>Administrator</th><th>Action</th><th>Account</th><th>HTTP</th><th>Detail</th></tr></thead>
          <tbody>{rows.map((r) => (
            <tr key={r.id}><td>{day(r.at)}</td><td>{r.admin_email}</td>
              <td>{r.detail?.attempt_on_account ? "failed login attempt on this account" : r.action}</td>
              <td>{r.target_user_id ? <Link to={`/admin/users/${r.target_user_id}`}>#{r.target_user_id}</Link> : ""}</td>
              <td>{r.status ?? ""}</td><td className="muted">{detail(r.detail)}</td></tr>
          ))}</tbody></table>
      </div>
    </>
  );
}
