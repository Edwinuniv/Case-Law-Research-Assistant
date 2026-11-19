// The admin menu, on the left of every admin page. Pages are only reachable for admins:
// the server refuses /admin (401/403) and every /api/admin call.
// While an admin page is open, the body gets the dark background of the dashboard (admin.css).
import { useEffect } from "react";
import { NavLink, Outlet } from "react-router-dom";
import logoMark from "../assets/logo-light.webp";   // the Verdicta logo, white V for the dark pages (Edwin, 2026-11-19; was the seal)
import "./admin.css";

const PAGES = [["", "Overview"], ["eval", "Evaluation"], ["questions", "Test questions"],
  ["abstentions", "Abstentions"], ["analytics", "Analytics"], ["settings", "Settings"],
  ["corpus", "Corpus & citations"], ["messages", "Messages"], ["users", "Accounts"],
  ["all-questions", "All questions"], ["log", "Admin log"]];          // the last two: Joe, SPEC 11, 2026-11-14

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
