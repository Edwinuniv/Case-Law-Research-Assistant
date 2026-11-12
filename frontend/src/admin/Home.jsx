// Overview: corpus counts, the latest evaluation (tune split), re-index, background jobs.
// Every number comes from GET /api/admin/home. The only fixed number is NFR3's target (0.80),
// a requirement of our requirements document, drawn as a tick on the dials, never as a result.
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { Dial, Kpi, Ring } from "./charts.jsx";
import { day, useLoad, Waiting } from "./useLoad.jsx";

const NFR3_TARGET = 0.8;          // abstention precision and recall each >= 0.80 (requirements document, NFR3)
const COUNT_LABELS = { decisions: "decisions", opinions: "opinions", chunks: "passages", citations: "citation table rows",
  citation_map: "citation map rows", questions: "test questions", queries_today: "questions asked today" };

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
      <h2>Overview of <em>Verdicta</em></h2>
      <p className="ad-lead">What is in the database, how the latest evaluation went on the tune split, and what is running.</p>
      <div className="ad-kpis">
        {Object.entries(d.counts).map(([k, v]) => <Kpi key={k} label={COUNT_LABELS[k] || k.replace("_", " ")} value={v} />)}
      </div>

      {m ? (
        <div className="ad-card">
          <h3>Latest evaluation: run {d.last_run}, tune split, current settings</h3>
          <div className="ad-row">
            <Kpi label="false citations shown" value={m.false_citations_shown} tone={m.false_citations_shown ? "bad" : "ok"}
                 sub={`of ${m.citations_shown} citations shown`} />
            <div className="ad-gauge"><Dial value={m.abstention_precision} target={NFR3_TARGET} label="Abstention precision" />
              <span>Abstention precision</span><small>white tick: target 0.80 (NFR3)</small></div>
            <div className="ad-gauge"><Dial value={m.abstention_recall} target={NFR3_TARGET} label="Abstention recall" />
              <span>Abstention recall</span><small>white tick: target 0.80 (NFR3)</small></div>
            <div className="ad-gauge"><Ring value={m["recall@5"]} label="Recall at 5" /><span>Recall@5</span><small>right decision in the top 5</small></div>
            <div className="ad-gauge"><Ring value={m.groundedness_judge} color="#34d399" label="Groundedness" /><span>Groundedness</span><small>the judge said yes</small></div>
          </div>
          <p><Link to={`/admin/eval/${d.last_run}`}>Open this run →</Link></p>
        </div>
      ) : <div className="ad-card">No evaluation yet. <Link to="/admin/eval">Run one</Link>.</div>}

      <div className="ad-two">
        <form className="ad-card" onSubmit={reindex}>
          <h3>Re-index</h3>
          <div className="ad-form">
            <label className="ad-field">Chunk size (words)
              <input type="number" min={150} max={600} style={{ width: 100 }} value={words || d.chunk_max_words}
                     onChange={(e) => setWords(e.target.value)} /></label>
            <button>Re-index + regression run</button>
          </div>
          {msg && <p className="muted">{msg}</p>}
          <p className="muted">Rebuilds chunks and embeddings from the opinions in the database, then runs every test
            question. Compare the new run with the previous one on the Evaluation page: worse metrics are flagged.</p>
        </form>

        <div className="ad-card">
          <h3>Background jobs</h3>
          <div className="ad-table">
            <table><thead><tr><th>#</th><th>Started</th><th>Kind</th><th>Status</th><th>Message</th></tr></thead>
              <tbody>{d.jobs.length === 0 ? <tr><td colSpan={5}>None yet.</td></tr> : d.jobs.map((j) => (
                <tr key={j.id} className={j.status === "failed" ? "red" : ""}>
                  <td>{j.id}</td><td>{day(j.created_at)}</td><td>{j.kind}</td>
                  <td>{j.status === "failed" ? <b>✕ failed</b> : j.status}</td><td>{j.message}</td></tr>
              ))}</tbody></table>
          </div>
          <button className="light" onClick={reload}>Refresh</button>
        </div>
      </div>
    </>
  );
}
