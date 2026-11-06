// Corpus: citation lookup (the week-1 gate), latest ingestion reports, decisions 100 at a time.
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { day, useLoad, Waiting } from "./useLoad.js";

function lookupClass(status) {          // in our corpus = green, exists elsewhere = yellow, else red
  if (status.includes("OUTSIDE")) return "LOW_CONFIDENCE";
  return status.includes("CORPUS") ? "ANSWERED" : "ERROR";
}

export default function Corpus() {
  const [p, setP] = useSearchParams();
  const cite = p.get("cite") || "";
  const offset = Number(p.get("offset") || 0);
  const [d, error] = useLoad(`/admin/corpus?cite=${encodeURIComponent(cite)}&offset=${offset}`);
  const [text, setText] = useState(cite);
  if (!d) return <Waiting data={d} error={error} />;
  const l = d.lookup;
  return (
    <>
      <h2>Corpus and citations</h2>
      <form className="card" onSubmit={(e) => { e.preventDefault(); setP({ cite: text }); }}>
        <h3>Citation lookup</h3>
        Citation <input value={text} onChange={(e) => setText(e.target.value)} placeholder="603 U.S. 593" /> <button>Check</button>
        {l && <div className={"status " + lookupClass(l.status)} style={{ marginTop: 8 }}>
          <b>{l.status}</b> — {l.citation}{l.cluster_id && <> → CourtListener cluster {l.cluster_id}</>}
          {l.decision_id && <> (our decision {l.decision_id})</>}</div>}
      </form>
      <div className="card"><h3>Latest ingestion reports</h3>
        <table><thead><tr><th>When</th><th>Kind</th><th>Report</th></tr></thead>
          <tbody>{d.reports.map((r) => (
            <tr key={r.id}><td>{day(r.created_at)}</td><td>{r.kind}</td><td><code>{JSON.stringify(r.report)}</code></td></tr>))}</tbody></table></div>
      <table><thead><tr><th>ID</th><th>Case</th><th>Filed</th><th>Citations</th><th>Licence</th><th>Loaded</th></tr></thead>
        <tbody>{d.decisions.map((x) => (
          <tr key={x.decision_id}><td>{x.decision_id}</td>
            <td><a href={x.source_url} target="_blank" rel="noreferrer">{x.case_name}</a></td><td>{x.date_filed}</td>
            <td>{x.citations.join(", ")}</td><td className="muted">{x.licence}</td><td className="muted">{day(x.loaded_at).slice(0, 10)}</td></tr>))}</tbody></table>
      <p>{offset > 0 && <button className="light" onClick={() => setP({ offset: offset - 100 })}>← previous 100</button>}{" "}
        <button className="light" onClick={() => setP({ offset: offset + 100 })}>next 100 →</button></p>
    </>
  );
}
