// Questions the system did not answer confidently: label each one, add real mistakes to the test set (SR43).
// Everything comes from GET /api/admin/abstentions (the latest 200 of the chosen status).
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api.js";
import { StatusBadge } from "./charts.jsx";
import { day, num, useLoad, Waiting } from "./useLoad.jsx";

const LABELS = [["correct", "Correct"], ["should have answered", "Should have answered"],
  ["add as unanswerable test question", "Add to test set (unanswerable)"],
  ["add as answerable test question", "Add to test set (answerable)"]];

const Score = ({ v, label }) => (
  <span className="ad-score">{label} <b>{num(v)}</b>
    {typeof v === "number" && <span className="ad-bar" aria-hidden="true"><i style={{ width: `${Math.max(0, Math.min(1, v)) * 100}%` }} /></span>}</span>
);

export default function Abstentions() {
  const [p, setP] = useSearchParams();
  const status = p.get("status") || "NOT_SUPPORTED";
  const [rows, error, reload] = useLoad(`/admin/abstentions?status=${status}`);
  const navigate = useNavigate();
  if (!rows) return <Waiting data={rows} error={error} />;

  async function label(id, value) {
    const r = await api(`/admin/abstentions/${id}/label`, { label: value });
    if (r.prefill) navigate(`/admin/questions/edit?${new URLSearchParams(r.prefill)}`);
    else reload();
  }

  return (
    <>
      <h2>Questions it did not answer <em>confidently</em></h2>
      <p className="ad-lead">Label each one, and add real mistakes to the test set: this is how abstention is tuned rather than guessed.</p>
      <div className="ad-card ad-form">
        <span className="muted">Show:</span>
        {["NOT_SUPPORTED", "LOW_CONFIDENCE", "ERROR"].map((s) => (
          <button key={s} className={`chip ${s === status ? "on" : ""}`} aria-pressed={s === status}
                  onClick={() => setP({ status: s })}>{s.replace("_", " ").toLowerCase()}</button>))}
        <span className="muted">{rows.length} shown{rows.length === 200 ? " (the latest 200)" : ""}</span>
      </div>
      {rows.length === 0 && <p className="muted">Nothing here yet.</p>}
      {rows.map((r) => (
        <div className="ad-card" key={r.id}>
          <div className="ad-form" style={{ justifyContent: "space-between" }}>
            <b>{r.question}</b><StatusBadge status={r.status} />
          </div>
          <p className="ad-form" style={{ margin: "10px 0" }}>
            <span className="muted">{day(r.created_at)}</span>
            <Score v={r.support_score} label="support" />
            <Score v={r.top_score} label="best passage" />
            {r.label && <span className="muted">label: <b>{r.label}</b></span>}
          </p>
          <p className="muted">{r.reason}</p>
          <details><summary>Passages ({r.passages.length}) and removed sentences ({r.removed.length})</summary>
            <ol>{r.passages.map((x) => (
              <li key={x.chunk_id}>{num(x.score)} — {x.case_name ? `${x.case_name} — ${x.label}` : `${x.chunk_id} (old index)`}</li>))}</ol>
            {r.removed.map((x, i) => <p key={i}>Removed: {x.text}<br /><b>{x.problems.join("; ")}</b></p>)}
          </details>
          <div className="ad-form" style={{ marginTop: 12 }}>{LABELS.map(([value, text]) => (
            <button key={value} className="light" onClick={() => label(r.id, value)}>{text}</button>))}</div>
        </div>
      ))}
    </>
  );
}
