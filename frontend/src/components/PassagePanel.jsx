// The side panel (SR31): the opinion around the passage, the quote highlighted, a link to CourtListener.
// Text is shown as text (React escapes it), never as HTML, so an opinion cannot inject a script.
import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";

export default function PassagePanel({ open }) {
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

  if (!open) return <div className="card panel"><p className="muted">Click a citation to read the passage in its opinion here.</p></div>;
  if (error) return <div className="card panel error">{error}</div>;
  if (!p) return <div className="card panel muted">Loading…</div>;
  return (
    <div className="card panel">
      <h3 style={{ marginTop: 0 }}>{p.case_name}</h3>
      <p className="muted">{p.citation} · filed {p.date_filed} · {p.opinion_label} · {p.section}<br />
        <a href={p.source_url} target="_blank" rel="noreferrer">Open on CourtListener</a> · {p.licence}</p>
      <div style={{ whiteSpace: "pre-wrap", fontSize: 14 }}>
        <span className="muted">…{p.before}</span>
        <span className="hl" ref={p.marked ? null : mark}>{p.inside_before}
          {p.marked && <mark ref={mark}>{p.marked}</mark>}{p.inside_after}</span>
        <span className="muted">{p.after}…</span>
      </div>
    </div>
  );
}
