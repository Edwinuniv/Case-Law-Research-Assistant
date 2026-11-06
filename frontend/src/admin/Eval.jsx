// Evaluation runs: start a run, compare two runs, the list with the main metrics (test split).
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { day, num, useLoad, Waiting } from "./useLoad.js";

export default function Eval() {
  const [runs, error, reload] = useLoad("/admin/eval");
  const [note, setNote] = useState("");
  const [cmp, setCmp] = useState({ a: "", b: "", split: "test" });
  const [msg, setMsg] = useState("");
  const navigate = useNavigate();
  if (!runs) return <Waiting data={runs} error={error} />;

  async function start(e) {
    e.preventDefault();
    try { const r = await api("/admin/eval/run", { note }); setMsg(`Started (job ${r.job}).`); reload(); }
    catch (err) { setMsg(err.message); }
  }

  return (
    <>
      <h2>Evaluation runs</h2>
      <div className="card">
        <form onSubmit={start}>Note <input value={note} onChange={(e) => setNote(e.target.value)}
                                           placeholder="e.g. baseline hybrid" style={{ width: 260 }} />{" "}
          <button>Run all test questions now</button> {msg && <span className="muted">{msg}</span>}</form>
        <p className="muted">Takes several minutes (about two model calls per question). Follow it under Background
          jobs on the Overview page.</p>
        <form onSubmit={(e) => { e.preventDefault(); navigate(`/admin/eval/compare?a=${cmp.a}&b=${cmp.b}&split=${cmp.split}`); }}>
          Compare run <input type="number" required style={{ width: 70 }} value={cmp.a}
                             onChange={(e) => setCmp({ ...cmp, a: e.target.value })} /> (before) with run{" "}
          <input type="number" required style={{ width: 70 }} value={cmp.b}
                 onChange={(e) => setCmp({ ...cmp, b: e.target.value })} /> (after){" "}
          <select value={cmp.split} onChange={(e) => setCmp({ ...cmp, split: e.target.value })}>
            <option value="test">test split</option><option value="tune">tune split</option><option value="">all</option>
          </select> <button className="light">Compare</button>
        </form>
      </div>
      <table>
        <thead><tr><th>Run</th><th>Date</th><th>Trigger</th><th>Note</th><th>Status</th><th>Recall@5</th><th>MRR@10</th>
          <th>Abst. P</th><th>Abst. R</th><th>False citations</th><th>Grounded</th></tr></thead>
        <tbody>{runs.map((r) => (
          <tr key={r.id}>
            <td><Link to={`/admin/eval/${r.id}`}>{r.id}</Link></td><td>{day(r.created_at)}</td><td>{r.trigger}</td>
            <td>{r.note}</td><td>{r.status}</td><td>{num(r.metrics["recall@5"])}</td><td>{num(r.metrics["mrr@10"])}</td>
            <td>{num(r.metrics.abstention_precision)}</td><td>{num(r.metrics.abstention_recall)}</td>
            <td className={r.metrics.false_citations_shown ? "red" : ""}>{num(r.metrics.false_citations_shown)}</td>
            <td>{num(r.metrics.groundedness_judge)}</td>
          </tr>
        ))}</tbody>
      </table>
      <p className="muted">Test split, current settings.</p>
    </>
  );
}
