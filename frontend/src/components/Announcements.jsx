// The announcements banner (Edwin, SPEC 11, 2026-11-20, from CedarPay): the messages an administrator posted that are
// active now, at the top of every page. A visitor may close one; it stays closed in this browser (localStorage).
import { useEffect, useState } from "react";
import { api } from "../api.js";
import "./announcements.css";

const KEY = "verdicta-closed-announcements";

function closedIds() {
  try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch { return []; }
}

export default function Announcements() {
  const [items, setItems] = useState([]);
  useEffect(() => {
    api("/announcements").then((all) => setItems(all.filter((a) => !closedIds().includes(a.id))), () => {});
  }, []);
  function close(id) {
    try { localStorage.setItem(KEY, JSON.stringify([...closedIds(), id].slice(-50))); } catch { /* private mode */ }
    setItems(items.filter((a) => a.id !== id));
  }
  if (!items.length) return null;
  return (
    <div className="ann" role="region" aria-label="Announcements">
      {items.map((a) => (
        <p key={a.id} className={`ann-item ann-${a.level}`} role={a.level === "warning" ? "alert" : "status"}>
          <span className="ann-icon" aria-hidden="true">{a.level === "warning" ? "⚠" : "✦"}</span>
          <span className="ann-text">{a.text}</span>
          <button className="ann-close" onClick={() => close(a.id)} aria-label="Close this announcement">×</button>
        </p>
      ))}
    </div>
  );
}
