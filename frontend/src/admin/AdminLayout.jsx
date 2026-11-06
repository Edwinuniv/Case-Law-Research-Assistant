// The admin menu, on the left of every admin page. Pages are only reachable for admins:
// the server refuses /admin (401/403) and every /api/admin call.
import { NavLink, Outlet } from "react-router-dom";

const PAGES = [["", "Overview"], ["eval", "Evaluation"], ["questions", "Test questions"],
  ["abstentions", "Abstentions"], ["analytics", "Analytics"], ["settings", "Settings"],
  ["corpus", "Corpus & citations"], ["users", "Accounts"]];

export default function AdminLayout({ user }) {
  return (
    <div className="admin">
      <nav className="side">
        <b>Administration</b>
        {PAGES.map(([path, name]) => (
          <NavLink key={path} end to={"/admin/" + path}>{name}</NavLink>
        ))}
        <span className="muted">{user.email}</span>
      </nav>
      <section><Outlet /></section>
    </div>
  );
}
