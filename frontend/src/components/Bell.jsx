// The notifications bell (Edwin, SPEC 11, 2026-11-20, from CedarPay's notifications): the number of unread notices,
// and the latest 20 when opened (which marks them read). Asks for new ones when the page opens and every minute while
// the tab is in front. The notices are written by the server for the same events as the emails.
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import "./bell.css";

function ago(iso) {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(iso).toLocaleDateString();
}

export default function Bell() {
  const [data, setData] = useState({ unread: 0, items: [] });
  const [open, setOpen] = useState(false);
  const box = useRef(null);

  useEffect(() => {
    const load = () => { if (document.visibilityState === "visible") api("/notifications").then(setData, () => {}); };
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (!open) return;
    const close = (e) => { if (e.key === "Escape" || (e.type === "mousedown" && !box.current?.contains(e.target))) setOpen(false); };
    document.addEventListener("keydown", close);
    document.addEventListener("mousedown", close);
    return () => { document.removeEventListener("keydown", close); document.removeEventListener("mousedown", close); };
  }, [open]);

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && data.unread) {
      await api("/notifications/read", {}).catch(() => {});
      setData({ ...data, unread: 0 });          // the list keeps its "new" marks until it is closed
    }
  }

  return (
    <div className="bell" ref={box}>
      <button className="bell-btn" onClick={toggle} aria-expanded={open}
              aria-label={data.unread ? `Notifications: ${data.unread} new` : "Notifications"}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
          <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" /></svg>
        {data.unread > 0 && <span className="bell-n">{data.unread > 9 ? "9+" : data.unread}</span>}
      </button>
      {open && (
        <div className="bell-panel" role="dialog" aria-label="Notifications">
          <b className="bell-title">Notifications</b>
          {data.items.length === 0 && <p className="bell-empty">Nothing yet. We tell you here when something changes in your account.</p>}
          <ul>
            {data.items.map((n) => (
              <li key={n.id} className={n.read ? "" : "new"}>
                {n.link ? <Link to={n.link} onClick={() => setOpen(false)}>{n.text}</Link> : <span>{n.text}</span>}
                <small>{ago(n.created_at)}</small>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
