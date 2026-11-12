// Corpus: citation lookup (the week-1 gate), latest ingestion reports, decisions 100 at a time.
// Everything comes from GET /api/admin/corpus.
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { day, useLoad, Waiting } from "./useLoad.jsx";

const LOOKUP = {                          // the four answers of the lookup (SR14): icon AND words, not colour alone
  "IN OUR CORPUS": ["✓", "ANSWERED"], "EXISTS OUTSIDE OUR CORPUS": ["◐", "LOW_CONFIDENCE"],
  "NOT FOUND": ["✕", "ERROR"], "CANNOT BE READ": ["?", "NOT_SUPPORTED"],
};

export default function Corpus() {
  const [p, setP] = useSearchParams();
  const cite = p.get("cite") || "";
  const offset = Number(p.get("offset") || 0);
  const [d, error] = useLoad(`/admin/corpus?cite=${encodeURIComponent(cite)}&offset=${offset}`);
  const [text, setText] = useState(cite);
  if (!d) return <Waiting data={d} error={error} />;
  const l = d.lookup;
  const [icon, cls] = (l && LOOKUP[l.status]) || ["?", "NOT_SUPPORTED"];
  return (
    <>
      <h2>Corpus and <em>citations</em></h2>
      <p className="ad-lead">Is a citation real, and is it one of our decisions? The same lookup the verifier uses (check 3).</p>
      <form className="ad-card" onSubmit={(e) => { e.preventDefault(); setP({ cite: text }); }}>
        <h3>Citation lookup</h3>
        <div className="ad-form">
          <label className="ad-field">Citation<input value={text} onChange={(e) => setText(e.target.value)} placeholder="554 U.S. 570" /></label>
          <button>Check</button>
        </div>
        {l && <p className={`ad-lookup ad-status st-${cls}`}><span aria-hidden="true">{icon}</span> {l.status} — {l.citation}
          {l.cluster_id && <> → CourtListener cluster {l.cluster_id}</>}{l.decision_id && <> (our decision {l.decision_id})</>}</p>}
      </form>
      <div className="ad-card"><h3>Latest ingestion reports</h3>
        <div className="ad-table"><table><thead><tr><th>When</th><th>Kind</th><th>Report</th></tr></thead>
          <tbody>{d.reports.map((r) => (
            <tr key={r.id}><td>{day(r.created_at)}</td><td>{r.kind}</td><td><code>{JSON.stringify(r.report)}</code></td></tr>))}</tbody></table></div></div>
      <div className="ad-card"><h3>Decisions {offset + 1} to {offset + d.decisions.length}, newest first</h3>
        <div className="ad-table wide"><table><thead><tr><th>ID</th><th>Case</th><th>Filed</th><th>Citations</th><th>Licence</th><th>Loaded</th></tr></thead>
          <tbody>{d.decisions.map((x) => (
            <tr key={x.decision_id}><td>{x.decision_id}</td>
              <td><a href={x.source_url} target="_blank" rel="noreferrer">{x.case_name}</a></td><td>{x.date_filed}</td>
              <td>{x.citations.join(", ")}</td><td className="muted">{x.licence}</td><td className="muted">{day(x.loaded_at).slice(0, 10)}</td></tr>))}</tbody></table></div>
        <div className="ad-form">{offset > 0 && <button className="light" onClick={() => setP({ offset: offset - 100 })}>← previous 100</button>}
          <button className="light" onClick={() => setP({ offset: offset + 100 })}>next 100 →</button></div>
      </div>
    </>
  );
}
