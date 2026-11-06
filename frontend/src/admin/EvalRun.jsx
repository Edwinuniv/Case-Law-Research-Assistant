// One evaluation run: metrics, a what-if threshold (does not change the live system),
// the threshold sweep on the tune split, and every question (wrong outcomes first).
import { useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { num, useLoad, Waiting } from "./useLoad.js";

export default function EvalRun() {
  const { runId } = useParams();
  const [params, setParams] = useSearchParams();
  const split = params.get("split") || "test";
  const tau = params.get("tau");
  const [d, error] = useLoad(`/admin/eval/${runId}?split=${split}${tau ? `&tau=${tau}` : ""}`);
  const [form, setForm] = useState({ tau: tau || "", split });
  if (!d) return <Waiting data={d} error={error} />;

  return (
    <>
      <h2>Evaluation run {d.run_id}</h2>
      <form className="card" onSubmit={(e) => { e.preventDefault(); setParams(form.tau ? form : { split: form.split }); }}>
        What-if abstention threshold <input type="number" step="0.01" style={{ width: 80 }} placeholder={d.tau_abstain}
                                            value={form.tau} onChange={(e) => setForm({ ...form, tau: e.target.value })} />{" "}
        Split <select value={form.split} onChange={(e) => setForm({ ...form, split: e.target.value })}>
          <option>test</option><option>tune</option></select>{" "}
        <button className="light">Recalculate</button> <span className="muted">This does not change the live system.</span>
      </form>
      <div className="two">
        <table><thead><tr><th>Metric ({d.split} split)</th><th>Value</th></tr></thead>
          <tbody>{Object.entries(d.metrics).map(([k, v]) => (
            <tr key={k} className={k.startsWith("false_citation") && v ? "red" : ""}><td>{k.replaceAll("_", " ")}</td><td>{num(v)}</td></tr>
          ))}</tbody></table>
        <div className="card"><h3 style={{ marginTop: 0 }}>Threshold sweep (tune split)</h3>
          <table><thead><tr><th>τ</th><th>Precision</th><th>Recall</th><th>Wrong abst.</th><th>Wrong ans.</th></tr></thead>
            <tbody>{d.sweep.map((x) => (
              <tr key={x.tau} className={Math.abs(x.tau - d.tau_abstain) < 0.011 ? "hl" : ""}>
                <td>{x.tau}</td><td>{num(x.precision)}</td><td>{num(x.recall)}</td><td>{x.wrong_abstentions}</td><td>{x.wrong_answers}</td></tr>
            ))}</tbody></table></div>
      </div>
      <div className="card"><h3>Questions (wrong outcomes first)</h3>
        <table><thead><tr><th>ID</th><th>Tag / split</th><th>Question</th><th>Status</th><th>Support</th>
          <th>Removed / fabrications caught</th><th>False shown</th><th>Judge</th></tr></thead>
          <tbody>{d.table.map((t) => (
            <tr key={t.id} className={t.ok ? "" : "red"}>
              <td>{t.id}</td><td>{t.tag}<br /><span className="muted">{t.split}</span></td>
              <td>{t.question}
                {t.removed.length > 0 && <details><summary className="muted">removed sentences</summary>
                  {t.removed.map((x, i) => <p key={i}>{x.text}<br /><b>{x.problems.join("; ")}</b></p>)}</details>}</td>
              <td>{t.status}</td><td>{num(t.support_score)}</td><td>{t.n_removed} / {t.fabrications_caught}</td>
              <td className={t.false ? "red" : ""}>{t.false}</td><td>{t.judgements.join(", ")}</td>
            </tr>
          ))}</tbody></table></div>
    </>
  );
}
