// Test questions: filter by tag, add, edit, export questions.jsonl (to commit in git).
// The list and the counts come from GET /api/admin/questions.
import { Link, useSearchParams } from "react-router-dom";
import { useLoad, Waiting } from "./useLoad.jsx";

const TAGS = ["", "answerable", "unanswerable", "adversarial"];

export default function Questions() {
  const [p, setP] = useSearchParams();
  const tag = p.get("tag") || "";
  const [qs, error] = useLoad(`/admin/questions?tag=${tag}`);
  if (!qs) return <Waiting data={qs} error={error} />;
  const splits = { tune: qs.filter((q) => q.split === "tune").length, test: qs.filter((q) => q.split === "test").length };
  return (
    <>
      <h2>Test <em>questions</em></h2>
      <p className="ad-lead">{qs.length} {tag || "questions"} shown: {splits.tune} tune, {splits.test} test.
        Changing a question changes eval-v1: export the file and commit it, so the change is in the git history.</p>
      <div className="ad-card ad-form">
        <Link to="/admin/questions/edit">+ Add a question</Link>
        {/* a normal link: the browser downloads the file (the session cookie goes with it) */}
        <a href="/api/admin/questions/export">Export questions.jsonl</a>
        <span className="muted">Show:</span>
        {TAGS.map((t) => (
          <button key={t} className={`chip ${t === tag ? "on" : ""}`} aria-pressed={t === tag}
                  onClick={() => setP(t ? { tag: t } : {})}>{t || "all"}</button>))}
      </div>
      <div className="ad-table wide">
        <table><thead><tr><th>ID</th><th>Tag</th><th>Split</th><th>Question</th><th>Expected decisions</th><th>Author</th><th></th></tr></thead>
          <tbody>{qs.map((q) => (
            <tr key={q.id}><td><b>{q.id}</b></td><td>{q.tag}</td><td>{q.split}</td><td>{q.question}</td>
              <td>{q.gold_decision_ids.join(", ")}</td><td>{q.author}</td>
              <td><Link to={`/admin/questions/edit?id=${encodeURIComponent(q.id)}`}>Edit</Link></td></tr>
          ))}</tbody></table>
      </div>
    </>
  );
}
