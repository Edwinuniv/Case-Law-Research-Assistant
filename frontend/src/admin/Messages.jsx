// Contact messages sent through the Contact page (GET /api/admin/messages), newest first; an administrator
// answers by email and can delete a message (POST /api/admin/messages/{id}/delete), for example when asked to.
import { useState } from "react";
import { api } from "../api.js";
import { day, useLoad, Waiting } from "./useLoad.jsx";

export default function Messages() {
  const [list, error] = useLoad("/admin/messages");
  const [after, setAfter] = useState(null);          // the list after a deletion
  const [msg, setMsg] = useState("");
  const shown = after || list;
  if (!shown) return <Waiting data={list} error={error} />;

  async function remove(m) {
    if (!window.confirm(`Delete the message from ${m.name}? This cannot be undone.`)) return;
    try { setAfter(await api(`/admin/messages/${m.id}/delete`, {})); setMsg("Message deleted."); }
    catch (err) { setMsg(err.message); }
  }

  return (
    <>
      <h2>Contact <em>messages</em></h2>
      <p className="ad-lead">{shown.length} message(s) from the Contact page, newest first. Answer by email; delete a message
        when its sender asks (privacy page).</p>
      {msg && <p className="muted">{msg}</p>}
      {shown.length === 0 && <p className="muted">No message yet.</p>}
      {shown.map((m) => (
        <div className="ad-card" key={m.id}>
          <div className="ad-form" style={{ justifyContent: "space-between" }}>
            <span><b>{m.name}</b> · <a href={`mailto:${m.email}`}>{m.email}</a></span>
            <span className="muted">{day(m.created_at)}</span>
          </div>
          <p style={{ whiteSpace: "pre-wrap" }}>{m.message}</p>
          <button className="light" onClick={() => remove(m)}>Delete</button>
        </div>
      ))}
    </>
  );
}
