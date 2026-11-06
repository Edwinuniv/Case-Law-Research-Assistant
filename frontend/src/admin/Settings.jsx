// Settings: 1. preview new thresholds on the latest run (saves nothing, FR23); 2. save.
import { useEffect, useState } from "react";
import { api } from "../api.js";
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
  const numberInput = (k, step = "0.01", width = 80) => (
    <input type="number" step={step} style={{ width }} value={form[k]} onChange={(e) => set(k, e.target.value)} />);

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
      <h2>Settings</h2>
      <form className="card" onSubmit={showPreview}>
        <h3>1. Preview new thresholds on the latest evaluation run</h3>
        {FIELDS.map(([k, label]) => <span key={k}>{label} {numberInput(k)} </span>)}
        <button className="light">Preview</button>
        {preview && (
          <table style={{ marginTop: 10 }}>
            <thead><tr><th>Metric (run {preview.run}, {preview.split} split)</th><th>Current settings</th><th>New settings</th></tr></thead>
            <tbody>{preview.rows.map((r) => (
              <tr key={r.metric}><td>{r.metric.replaceAll("_", " ")}</td><td>{num(r.now)}</td><td>{num(r.then)}</td></tr>
            ))}</tbody>
          </table>
        )}
      </form>
      <form className="card" onSubmit={save}>
        <h3>2. Save</h3>
        <p>{FIELDS.map(([k, label]) => <span key={k}>{label} {numberInput(k)} · </span>)}</p>
        <p>Passages after search {numberInput("retrieve_k", "1", 60)} · Passages given to the model {numberInput("top_k", "1", 60)} ·{" "}
          <label><input type="checkbox" checked={!!form.use_reranker} onChange={(e) => set("use_reranker", e.target.checked)} />
            {" "}Use the reranker (week-10 improvement)</label></p>
        <button>Save settings</button> {msg && <span className="muted">{msg}</span>}
        <p className="muted">Choose thresholds on the tune split (the sweep table of an evaluation run and this preview).
          Report the test split once, at the end, without changing them (EVALUATION.md).</p>
      </form>
    </>
  );
}
