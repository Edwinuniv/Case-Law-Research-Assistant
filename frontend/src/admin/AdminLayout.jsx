// The admin menu, on the left of every admin page. Pages are only reachable for admins:
// the server refuses /admin (401/403) and every /api/admin call.
// While an admin page is open, the body gets the dark background of the dashboard (admin.css).
import { useEffect } from "react";
import { NavLink, Outlet } from "react-router-dom";
import logoMark from "../assets/logo-seal.webp";   // the Verdicta seal (Yasser, 2026-11-12)
import "./admin.css";

const PAGES = [["", "Overview"], ["eval", "Evaluation"], ["questions", "Test questions"],
  ["abstentions", "Abstentions"], ["analytics", "Analytics"], ["settings", "Settings"],
  ["corpus", "Corpus & citations"], ["messages", "Messages"], ["users", "Accounts"]];

export default function AdminLayout({ user }) {
  useEffect(() => {
    document.body.classList.add("ad-dark");
    return () => document.body.classList.remove("ad-dark");
  }, []);
  return (
    <div className="ad">
      <nav className="ad-side" aria-label="Administration">
        <div className="ad-brand"><img src={logoMark} alt="" /><div><b>Verdicta</b><small>Administration</small></div></div>
        {PAGES.map(([path, name]) => (
          <NavLink key={path} end={path === ""} to={"/admin/" + path}><i aria-hidden="true" />{name}</NavLink>
        ))}
        <span className="ad-who">{user.email}</span>
      </nav>
      <section><Outlet /></section>
    </div>
  );
}
