// Add or edit one test question. ?id=X edits X; ?question=...&tag=... prefills a new one
// (from the abstentions page, SR43). After saving: export and commit eval/questions.jsonl.
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api.js";

const EMPTY = { id: "", tag: "answerable", split: "tune", question: "", expected_answer: "", gold_decision_ids: "",
  gold_quote: "", must_not_appear: "", why: "", author: "" };

export default function QuestionForm({ user }) {
  const [p] = useSearchParams();
  const editing = p.get("id");
  const [q, setQ] = useState(null);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    if (!editing) {
      setQ({ ...EMPTY, question: p.get("question") || "", tag: p.get("tag") || "answerable", author: user.email });
      return;
    }
    api(`/admin/questions/${encodeURIComponent(editing)}`)
      .then((x) => setQ({ ...x, gold_decision_ids: x.gold_decision_ids.join(" "), must_not_appear: x.must_not_appear.join("; "),
        expected_answer: x.expected_answer || "", gold_quote: x.gold_quote || "", why: x.why || "", author: x.author || "" }))
      .catch((e) => setError(e.message));
  }, [editing, p, user.email]);

  if (error) return <p className="error">{error}</p>;
  if (!q) return <p className="muted">Loading…</p>;
  const set = (k) => (e) => setQ({ ...q, [k]: e.target.value });

  async function save(e) {
    e.preventDefault(); setError("");
    const body = { ...q,
      gold_decision_ids: q.gold_decision_ids.replaceAll(",", " ").split(/\s+/).filter((x) => /^\d+$/.test(x)).map(Number),
      must_not_appear: q.must_not_appear.split(";").map((x) => x.trim()).filter(Boolean) };
    try { await api("/admin/questions", body); navigate("/admin/questions"); } catch (err) { setError(err.message); }
  }

  return (
    <form className="ad-card" onSubmit={save}>
      <h2>{editing ? "Edit" : "New"} test <em>question</em></h2>
      <div className="ad-form">
        <label className="ad-field">ID<input required value={q.id} readOnly={!!editing} onChange={set("id")} placeholder="e.g. G061" /></label>
        <label className="ad-field">Tag<select value={q.tag} onChange={set("tag")}>{["answerable", "unanswerable", "adversarial"].map((t) => <option key={t}>{t}</option>)}</select></label>
        <label className="ad-field">Split<select value={q.split} onChange={set("split")}><option>tune</option><option>test</option></select></label>
        <label className="ad-field">Author<input value={q.author} onChange={set("author")} /></label>
      </div>
      <p><label className="ad-field">Question<textarea rows={2} required value={q.question} onChange={set("question")} /></label></p>
      <p><label className="ad-field">Expected answer (answerable only)<textarea rows={2} value={q.expected_answer} onChange={set("expected_answer")} /></label></p>
      <p><label className="ad-field">Expected decision IDs (space separated)<input value={q.gold_decision_ids} onChange={set("gold_decision_ids")} /></label></p>
      <p><label className="ad-field">Gold quote (copied exactly from the opinion)<textarea rows={2} value={q.gold_quote} onChange={set("gold_quote")} /></label></p>
      <p><label className="ad-field">Must never appear (adversarial; separate with ;)<input value={q.must_not_appear} onChange={set("must_not_appear")} /></label></p>
      <p><label className="ad-field">Why unanswerable / notes<textarea rows={2} value={q.why} onChange={set("why")} /></label></p>
      {error && <p className="error" role="alert">{error}</p>}
      <p><button>Save</button> <span className="muted">Then export the questions and commit eval/questions.jsonl, so the change is in the git history.</span></p>
    </form>
  );
}
