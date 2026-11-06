// The admin menu, shown above every admin page. Pages are only reachable for admins:
// the server refuses /admin (401/403) and every /api/admin call.
import { NavLink, Outlet } from "react-router-dom";

const PAGES = [["", "Overview"], ["eval", "Evaluation"], ["questions", "Test questions"],
  ["abstentions", "Abstentions"], ["analytics", "Analytics"], ["settings", "Settings"],
  ["corpus", "Corpus & citations"], ["users", "Accounts"]];

export default function AdminLayout({ user }) {
  return (
    <>
      <div className="card" style={{ padding: "8px 14px" }}>
        <b>Admin</b>{" "}
        {PAGES.map(([path, name]) => (
          <span key={path}> · <NavLink end to={"/admin/" + path}>{name}</NavLink></span>
        ))}
        <span className="muted" style={{ float: "right" }}>{user.email}</span>
      </div>
      <Outlet />
    </>
  );
}
