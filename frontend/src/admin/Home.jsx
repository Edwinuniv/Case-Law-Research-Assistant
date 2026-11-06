// Overview: corpus counts, the latest evaluation (test split), re-index, background jobs.
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { day, num, useLoad, Waiting } from "./useLoad.jsx";

export default function Home() {
  const [d, error, reload] = useLoad("/admin/home");
  const [words, setWords] = useState("");
  const [msg, setMsg] = useState("");
  if (!d) return <Waiting data={d} error={error} />;
  const m = d.metrics;

  async function reindex(e) {
    e.preventDefault();
    if (!window.confirm("Rebuild all chunks and embeddings, then run the full evaluation automatically?")) return;
    try {
      const r = await api("/admin/reindex", { max_words: Number(words || d.chunk_max_words) });
      setMsg(`Started (job ${r.job}). Follow it below.`); reload();
    } catch (err) { setMsg(err.message); }
  }

  return (
    <>
      <h2>Overview</h2>
      <div className="grid">
        {Object.entries(d.counts).map(([k, v]) => (
          <div className="stat" key={k}>{k.replace("_", " ")}<b>{v.toLocaleString()}</b></div>
        ))}
      </div>
      {m ? (
        <div className="card">
          <h3>Latest evaluation (run {d.last_run}, test split, current settings)</h3>
          <div className="grid">
            <div className={"stat " + (m.false_citations_shown ? "red" : "green")}>False citations shown<b>{m.false_citations_shown}</b></div>
            <div className="stat">Abstention precision<b>{num(m.abstention_precision)}</b></div>
            <div className="stat">Abstention recall<b>{num(m.abstention_recall)}</b></div>
            <div className="stat">Recall@5<b>{num(m["recall@5"])}</b></div>
            <div className="stat">Groundedness (judge)<b>{num(m.groundedness_judge)}</b></div>
          </div>
          <Link to={`/admin/eval/${d.last_run}`}>Open this run</Link>
        </div>
      ) : <div className="card">No evaluation yet. <Link to="/admin/eval">Run one</Link>.</div>}

      <form className="card" onSubmit={reindex}>
        <h3>Re-index</h3>
        Chunk size (words) <input type="number" min={150} max={600} style={{ width: 80 }}
                                  value={words || d.chunk_max_words} onChange={(e) => setWords(e.target.value)} />{" "}
        <button>Re-index + regression run</button> {msg && <span className="muted">{msg}</span>}
        <p className="muted">Rebuilds chunks and embeddings from the opinions in the database, then runs every test
          question. Compare the new run with the previous one on the Evaluation page: worse metrics are shown in red.</p>
      </form>

      <div className="card">
        <h3>Background jobs</h3>
        <table><thead><tr><th>#</th><th>Started</th><th>Kind</th><th>Status</th><th>Message</th></tr></thead>
          <tbody>{d.jobs.map((j) => (
            <tr key={j.id} className={j.status === "failed" ? "red" : ""}>
              <td>{j.id}</td><td>{day(j.created_at)}</td><td>{j.kind}</td><td>{j.status}</td><td>{j.message}</td></tr>
          ))}</tbody></table>
        <p><button className="light" onClick={reload}>Refresh</button></p>
      </div>
    </>
  );
}
