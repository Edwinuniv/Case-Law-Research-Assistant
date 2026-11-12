// The side panel (SR31): the opinion around the passage, the quote highlighted, a link to CourtListener.
// It slides in from the right over the page; Escape, the × button or a click outside closes it.
// Text is shown as text (React escapes it), never as HTML, so an opinion cannot inject a script.
import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";

export default function PassagePanel({ open, onClose }) {
  const [p, setP] = useState(null);
  const [error, setError] = useState("");
  const mark = useRef(null);

  useEffect(() => {
    if (!open) return;
    setP(null); setError("");
    api(`/passage/${encodeURIComponent(open.chunkId)}?quote=${encodeURIComponent(open.quote || "")}`)
      .then(setP).catch((e) => setError(e.message));
  }, [open]);

  useEffect(() => { mark.current?.scrollIntoView({ block: "center" }); }, [p]);

  useEffect(() => {
    const esc = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);

  return (
    <>
      <div className={`rs-backdrop ${open ? "on" : ""}`} onClick={onClose} />
      <aside className={`rs-drawer ${open ? "on" : ""}`} aria-hidden={!open} aria-label="Passage">
        <button className="rs-close" onClick={onClose} aria-label="Close">×</button>
        {error && <p className="error">{error}</p>}
        {open && !p && !error && <p className="muted">Loading the opinion…</p>}
        {p && (
          <>
            <span className="rs-kicker">{p.opinion_label}{p.section ? ` · ${p.section}` : ""}</span>
            <h3>{p.case_name}</h3>
            <p className="rs-cit">{p.citation} · filed {p.date_filed}</p>
            <a className="rs-cl" href={p.source_url} target="_blank" rel="noreferrer">Open on CourtListener ↗</a>
            <div className="rs-opinion">
              <span className="muted">…{p.before}</span>
              <span className="hl" ref={p.marked ? null : mark}>{p.inside_before}
                {p.marked && <mark ref={mark}>{p.marked}</mark>}{p.inside_after}</span>
              <span className="muted">{p.after}…</span>
            </div>
            <p className="muted rs-licence">{p.licence}</p>
          </>
        )}
      </aside>
    </>
  );
}
