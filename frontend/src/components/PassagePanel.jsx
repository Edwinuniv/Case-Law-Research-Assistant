// The side panel (SR31): the real opinion around the passage, the quote highlighted, a link to CourtListener.
// It slides in from the right over the page; Escape, the × button or a click outside closes it.
// Text is shown as text (React escapes it), never as HTML, so an opinion cannot inject a script.
// Props from pages/Chat.jsx: open ({chunkId, quote} or null), onClose().
import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import "./answer.css";

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
      <div className={`an-backdrop ${open ? "on" : ""}`} onClick={onClose} />
      <aside className={`an-drawer ${open ? "on" : ""}`} aria-hidden={!open} aria-label="Passage">
        <button className="an-close" onClick={onClose} aria-label="Close">×</button>
        {error && <p className="error">{error}</p>}
        {open && !p && !error && <p className="an-dim">Loading the opinion…</p>}
        {p && (
          <>
            <span className="an-kicker">{p.opinion_label}{p.section ? ` · ${p.section}` : ""}</span>
            <h3>{p.case_name}</h3>
            <p className="an-cit">{p.citation} · filed {p.date_filed}</p>
            <a className="an-cl" href={p.source_url} target="_blank" rel="noreferrer">Open on CourtListener ↗</a>
            {p.marked && <p className="an-dim">The highlighted words are the quote the sentence relies on.</p>}
            <div className="an-opinion">
              <span className="an-dim">…{p.before}</span>
              <span className="an-hl" ref={p.marked ? null : mark}>{p.inside_before}
                {p.marked && <mark ref={mark}>{p.marked}</mark>}{p.inside_after}</span>
              <span className="an-dim">{p.after}…</span>
            </div>
            <p className="an-dim an-licence">{p.licence}</p>
          </>
        )}
      </aside>
    </>
  );
}
