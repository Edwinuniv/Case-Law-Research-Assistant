// Evaluation runs: start a run, compare two runs, the list with the main metrics (tune split).
// Every number comes from GET /api/admin/eval (each run's metrics on the tune split, current settings).
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { Lines, OK, AMBER } from "./charts.jsx";
import { day, num, useLoad, Waiting } from "./useLoad.jsx";

const Bar = ({ v }) => (typeof v === "number"
  ? <span className="ad-bar" aria-hidden="true"><i style={{ width: `${Math.max(0, Math.min(1, v)) * 100}%` }} /></span> : null);

export default function Eval() {
  const [runs, error, reload] = useLoad("/admin/eval");
  const [note, setNote] = useState("");
  const [cmp, setCmp] = useState({ a: "", b: "", split: "tune" });
  const [msg, setMsg] = useState("");
  const navigate = useNavigate();
  if (!runs) return <Waiting data={runs} error={error} />;

  async function start(e) {
    e.preventDefault();
    try { const r = await api("/admin/eval/run", { note }); setMsg(`Started (job ${r.job}).`); reload(); }
    catch (err) { setMsg(err.message); }
  }

  // oldest first, finished runs only: abstention precision and recall of each run
  const done = runs.filter((r) => r.status === "done").slice().reverse()
    .map((r) => ({ id: r.id, precision: r.metrics.abstention_precision, recall: r.metrics.abstention_recall }));

  return (
    <>
      <h2>Evaluation <em>runs</em></h2>
      <p className="ad-lead">Every run sends all test questions through the real pipeline. Numbers below are on the tune split,
        with the current settings; the test split is reported once, at the end (open a run and choose test).</p>

      <div className="ad-two">
        <div className="ad-card">
          <h3>Run or compare</h3>
          <form className="ad-form" onSubmit={start}>
            <label className="ad-field">Note<input value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. baseline hybrid" /></label>
            <button>Run all test questions now</button>
          </form>
          {msg && <p className="muted">{msg}</p>}
          <p className="muted">Takes several minutes (about two model calls per question). Follow it under Background jobs on the Overview page.</p>
          <form className="ad-form" onSubmit={(e) => { e.preventDefault(); navigate(`/admin/eval/compare?a=${cmp.a}&b=${cmp.b}&split=${cmp.split}`); }}>
            <label className="ad-field">Before (run)<input type="number" required style={{ width: 90 }} value={cmp.a}
                                                          onChange={(e) => setCmp({ ...cmp, a: e.target.value })} /></label>
            <label className="ad-field">After (run)<input type="number" required style={{ width: 90 }} value={cmp.b}
                                                         onChange={(e) => setCmp({ ...cmp, b: e.target.value })} /></label>
            <label className="ad-field">Split<select value={cmp.split} onChange={(e) => setCmp({ ...cmp, split: e.target.value })}>
              <option value="tune">tune</option><option value="test">test</option><option value="">all</option></select></label>
            <button className="light">Compare</button>
          </form>
        </div>
        <div className="ad-card">
          <h3>Abstention, run by run (tune)</h3>
          {done.length > 0
            ? <Lines data={done} x="id" maxY={1} keys={[["precision", "precision", AMBER], ["recall", "recall", OK]]} />
            : <p className="muted">No finished run yet.</p>}
          <p className="muted">From the oldest finished run (left) to the newest (right): {done.map((r) => `run ${r.id}`).join(", ")}.</p>
        </div>
      </div>

      <div className="ad-table">
        <table>
          <thead><tr><th>Run</th><th>Date</th><th>Trigger</th><th>Note</th><th>Status</th><th>Recall@5</th><th>MRR@10</th>
            <th>Abst. precision</th><th>Abst. recall</th><th>False citations</th><th>Grounded</th></tr></thead>
          <tbody>{runs.map((r) => (
            <tr key={r.id}>
              <td><Link to={`/admin/eval/${r.id}`}><b>{r.id}</b></Link></td><td>{day(r.created_at)}</td><td>{r.trigger}</td>
              <td>{r.note}</td><td>{r.status}</td><td>{num(r.metrics["recall@5"])}</td><td>{num(r.metrics["mrr@10"])}</td>
              <td>{num(r.metrics.abstention_precision)}<Bar v={r.metrics.abstention_precision} /></td>
              <td>{num(r.metrics.abstention_recall)}<Bar v={r.metrics.abstention_recall} /></td>
              <td className={r.metrics.false_citations_shown ? "red" : ""}>{num(r.metrics.false_citations_shown)}</td>
              <td>{num(r.metrics.groundedness_judge)}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </>
  );
}
