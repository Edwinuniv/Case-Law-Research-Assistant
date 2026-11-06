// Questions the system did not answer confidently: label each one, add real mistakes to the test set (SR43).
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api.js";
import { day, num, useLoad, Waiting } from "./useLoad.js";

const LABELS = [["correct", "Correct"], ["should have answered", "Should have answered"],
  ["add as unanswerable test question", "Add to test set (unanswerable)"],
  ["add as answerable test question", "Add to test set (answerable)"]];

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
      <h2>Questions the system did not answer confidently</h2>
      <div className="card">Show:{" "}
        {["NOT_SUPPORTED", "LOW_CONFIDENCE", "ERROR"].map((s) => (
          <button key={s} className="chip" onClick={() => setP({ status: s })}>{s.replace("_", " ").toLowerCase()}</button>))}
        <span className="muted"> Use these to tune abstention: label each one, and add real mistakes to the test set.</span>
      </div>
      {rows.length === 0 && <p>Nothing here yet.</p>}
      {rows.map((r) => (
        <div className="card" key={r.id}>
          <b>{r.question}</b><br />
          <span className="muted">{day(r.created_at)} · {r.status} · support {num(r.support_score)} · best passage {num(r.top_score)} · {r.reason}
            {r.label && <> · label: <b>{r.label}</b></>}</span>
          <details><summary>Passages and removed sentences</summary>
            <ol>{r.passages.map((x) => (
              <li key={x.chunk_id}>{x.score} — {x.case_name ? `${x.case_name} — ${x.label}` : `${x.chunk_id} (old index)`}</li>))}</ol>
            {r.removed.map((x, i) => <p key={i}>Removed: {x.text}<br /><b>{x.problems.join("; ")}</b></p>)}
          </details>
          <p>{LABELS.map(([value, text]) => (
            <button key={value} className="light" style={{ marginRight: 6 }} onClick={() => label(r.id, value)}>{text}</button>))}</p>
        </div>
      ))}
    </>
  );
}
