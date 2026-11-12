// Settings: 1. preview new thresholds on the latest run (saves nothing, FR23); 2. save.
// The preview numbers come from GET /api/admin/settings/preview (tune split); the values from GET /api/admin/settings.
import { useEffect, useState } from "react";
import { api } from "../api.js";
import { PairBars, RATE_METRICS } from "./charts.jsx";
import { num, useLoad, Waiting } from "./useLoad.jsx";

const FIELDS = [["tau_abstain", "Abstain below support score"], ["tau_confident", "Low confidence below"],
  ["min_retrieval", "Minimum passage similarity"]];

export default function Settings() {
  const [s, error] = useLoad("/admin/settings");
  const [form, setForm] = useState(null);
  const [preview, setPreview] = useState(null);
  const [msg, setMsg] = useState("");
  useEffect(() => { if (s) setForm(s); }, [s]);
  if (!form) return <Waiting data={s} error={error} />;

  const set = (k, v) => setForm({ ...form, [k]: v });
  const numberInput = (k, label, step = "0.01", width = 110) => (
    <label className="ad-field" key={k}>{label}
      <input type="number" step={step} style={{ width }} value={form[k]} onChange={(e) => set(k, e.target.value)} /></label>);

  async function showPreview(e) {
    e.preventDefault(); setMsg("");
    const q = new URLSearchParams({ tau_abstain: form.tau_abstain, tau_confident: form.tau_confident,
      min_retrieval: form.min_retrieval });
    try { setPreview(await api(`/admin/settings/preview?${q}`)); } catch (err) { setMsg(err.message); }
  }

  async function save(e) {
    e.preventDefault();
    if (!window.confirm("Change the live system?")) return;
    const body = { ...form, tau_abstain: +form.tau_abstain, tau_confident: +form.tau_confident,
      min_retrieval: +form.min_retrieval, top_k: +form.top_k, retrieve_k: +form.retrieve_k };
    try { setForm(await api("/admin/settings", body)); setMsg("Saved."); } catch (err) { setMsg(err.message); }
  }

  return (
    <>
      <h2>Settings and <em>thresholds</em></h2>
      <p className="ad-lead">Choose thresholds on the tune split (the sweep of an evaluation run and the preview below).
        Report the test split once, at the end, without changing them (EVALUATION.md).</p>

      <form className="ad-card" onSubmit={showPreview}>
        <h3>1. Preview new thresholds on the latest evaluation run</h3>
        <div className="ad-form">
          {FIELDS.map(([k, label]) => numberInput(k, label))}
          <button className="light">Preview</button>
        </div>
        <p className="muted">The preview saves nothing.</p>
        {preview && (
          <div className="ad-table">
            <table>
              <thead><tr><th>Metric (run {preview.run}, {preview.split} split)</th><th>Current settings</th><th>New settings</th></tr></thead>
              <tbody>{preview.rows.map((r) => (
                <tr key={r.metric}><td>{r.metric.replaceAll("_", " ")}</td><td>{num(r.now)}</td>
                  <td>{num(r.then)}{RATE_METRICS.has(r.metric) && <PairBars a={r.now} b={r.then} />}</td></tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </form>

      <form className="ad-card" onSubmit={save}>
        <h3>2. Save (changes the live system)</h3>
        <div className="ad-form">{FIELDS.map(([k, label]) => numberInput(k, label))}</div>
        <div className="ad-form" style={{ marginTop: 12 }}>
          {numberInput("retrieve_k", "Passages after search", "1", 90)}
          {numberInput("top_k", "Passages given to the model", "1", 90)}
          <label><input type="checkbox" checked={!!form.use_reranker} onChange={(e) => set("use_reranker", e.target.checked)} />
            {" "}Use the reranker (week-10 improvement)</label>
        </div>
        <p><button>Save settings</button> {msg && <span className="muted">{msg}</span>}</p>
      </form>
    </>
  );
}
