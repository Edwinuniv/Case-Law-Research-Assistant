// One evaluation run: metrics, a what-if threshold (does not change the live system),
// the threshold sweep on the tune split, and every question (wrong outcomes first).
// Every number comes from GET /api/admin/eval/{id}. The tune split is shown unless the admin chooses test.
import { useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { AMBER, Dial, Kpi, Lines, OK, Ring, StatusBadge } from "./charts.jsx";
import { num, useLoad, Waiting } from "./useLoad.jsx";

const NFR3_TARGET = 0.8;          // requirements document, NFR3: abstention precision and recall each >= 0.80

export default function EvalRun() {
  const { runId } = useParams();
  const [params, setParams] = useSearchParams();
  const split = params.get("split") || "tune";
  const tau = params.get("tau");
  const [d, error] = useLoad(`/admin/eval/${runId}?split=${split}${tau ? `&tau=${tau}` : ""}`);
  const [form, setForm] = useState({ tau: tau || "", split });
  if (!d) return <Waiting data={d} error={error} />;
  const m = d.metrics;
  // the questions of the shown split, plus every adversarial question: the same ones the metrics use (SR29)
  const rows = d.table.filter((t) => t.split === d.split || t.tag === "adversarial");
  const wrong = rows.filter((t) => !t.ok).length;

  return (
    <>
      <h2>Evaluation run <em>{d.run_id}</em></h2>
      <p className="ad-lead">{d.split} split, abstention threshold τ = {d.tau_abstain}{tau ? " (what-if)" : ""}.
        {d.split === "test" && " The test split is reported once, at the end, without changing the thresholds."}</p>

      <form className="ad-card ad-form" onSubmit={(e) => { e.preventDefault(); setParams(form.tau ? form : { split: form.split }); }}>
        <label className="ad-field">What-if abstention threshold
          <input type="number" step="0.01" style={{ width: 110 }} placeholder={d.tau_abstain} value={form.tau}
                 onChange={(e) => setForm({ ...form, tau: e.target.value })} /></label>
        <label className="ad-field">Split<select value={form.split} onChange={(e) => setForm({ ...form, split: e.target.value })}>
          <option>tune</option><option>test</option></select></label>
        <button className="light">Recalculate</button>
        <span className="muted">This does not change the live system.</span>
      </form>

      <div className="ad-kpis">
        <Kpi label="false citations shown" value={m.false_citations_shown} tone={m.false_citations_shown ? "bad" : "ok"}
             sub={`of ${m.citations_shown} citations shown`} />
        <Kpi label="questions" value={m.questions} sub={`${m.answerable} answerable · ${m.unanswerable} unanswerable · ${m.adversarial} adversarial`} />
        <Kpi label="wrong outcomes" value={wrong} tone={wrong ? "bad" : "ok"} sub="in the table below" />
        <Kpi label="low confidence" value={m.low_confidence} />
        <Kpi label="errors" value={m.errors} tone={m.errors ? "bad" : "ok"} />
      </div>

      <div className="ad-card">
        <div className="ad-row">
          <div className="ad-gauge"><Dial value={m.abstention_precision} target={NFR3_TARGET} label="Abstention precision" />
            <span>Abstention precision</span><small>target 0.80 (NFR3)</small></div>
          <div className="ad-gauge"><Dial value={m.abstention_recall} target={NFR3_TARGET} label="Abstention recall" />
            <span>Abstention recall</span><small>target 0.80 (NFR3)</small></div>
          <div className="ad-gauge"><Ring value={m["recall@5"]} label="Recall at 5" /><span>Recall@5</span></div>
          <div className="ad-gauge"><Ring value={m["mrr@10"]} label="MRR at 10" /><span>MRR@10</span></div>
          <div className="ad-gauge"><Ring value={m.groundedness_judge} color={OK} label="Groundedness, judge" /><span>Groundedness (judge)</span></div>
          <div className="ad-gauge"><Ring value={m.adversarial_abstention_rate} color="#a78bfa" label="Adversarial abstention" /><span>Adversarial abstained</span></div>
        </div>
      </div>

      <div className="ad-two">
        <div className="ad-card">
          <h3>Threshold sweep (tune split)</h3>
          <Lines data={d.sweep} x="tau" maxY={1} marker={d.tau_abstain}
                 keys={[["precision", "abstention precision", AMBER], ["recall", "abstention recall", OK]]} />
          <p className="muted">τ from {d.sweep[0]?.tau} (left) to {d.sweep[d.sweep.length - 1]?.tau} (right); the dashed line is the τ used above.</p>
          <details><summary>The sweep as a table</summary>
            <div className="ad-table"><table><thead><tr><th>τ</th><th>Precision</th><th>Recall</th><th>Wrong abst.</th><th>Wrong ans.</th></tr></thead>
              <tbody>{d.sweep.map((x) => (
                <tr key={x.tau} className={Math.abs(x.tau - d.tau_abstain) < 0.011 ? "hl" : ""}>
                  <td>{x.tau}</td><td>{num(x.precision)}</td><td>{num(x.recall)}</td><td>{x.wrong_abstentions}</td><td>{x.wrong_answers}</td></tr>
              ))}</tbody></table></div></details>
        </div>
        <div className="ad-card">
          <h3>All metrics ({d.split} split)</h3>
          <div className="ad-table"><table><thead><tr><th>Metric</th><th>Value</th></tr></thead>
            <tbody>{Object.entries(m).map(([k, v]) => (
              <tr key={k} className={k.startsWith("false_citation") && v ? "red" : ""}><td>{k.replaceAll("_", " ")}</td><td>{num(v)}</td></tr>
            ))}</tbody></table></div>
        </div>
      </div>

      <div className="ad-card"><h3>Questions of the {d.split} split and the adversarial set, wrong outcomes first ({wrong} wrong)</h3>
        <div className="ad-table wide"><table><thead><tr><th>ID</th><th>Tag / split</th><th>Question</th><th>Status</th><th>Support</th>
          <th>Removed / fabrications caught</th><th>False shown</th><th>Judge</th></tr></thead>
          <tbody>{rows.map((t) => (
            <tr key={t.id} className={t.ok ? "" : "red"}>
              <td><b>{t.id}</b>{!t.ok && <><br /><span className="muted">✕ wrong</span></>}</td>
              <td>{t.tag}<br /><span className="muted">{t.split}</span></td>
              <td>{t.question}
                {t.removed.length > 0 && <details><summary>removed sentences</summary>
                  {t.removed.map((x, i) => <p key={i}>{x.text}<br /><b>{x.problems.join("; ")}</b></p>)}</details>}</td>
              <td><StatusBadge status={t.status} /></td><td>{num(t.support_score)}</td><td>{t.n_removed} / {t.fabrications_caught}</td>
              <td className={t.false ? "red" : ""}>{t.false}</td><td>{t.judgements.join(", ")}</td>
            </tr>
          ))}</tbody></table></div></div>
    </>
  );
}
