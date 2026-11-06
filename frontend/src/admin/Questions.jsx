// Test questions: filter by tag, add, edit, export questions.jsonl (to commit in git).
import { Link, useSearchParams } from "react-router-dom";
import { useLoad, Waiting } from "./useLoad.jsx";

export default function Questions() {
  const [p, setP] = useSearchParams();
  const tag = p.get("tag") || "";
  const [qs, error] = useLoad(`/admin/questions?tag=${tag}`);
  if (!qs) return <Waiting data={qs} error={error} />;
  return (
    <>
      <h2>Test questions ({qs.length})</h2>
      <div className="card">
        <Link to="/admin/questions/edit">Add a question</Link> ·{" "}
        {/* a normal link: the browser downloads the file (the session cookie goes with it) */}
        <a href="/api/admin/questions/export">Export questions.jsonl (to commit in git)</a>
        <span style={{ marginLeft: 12 }}>Show:{" "}
          {["", "answerable", "unanswerable", "adversarial"].map((t) => (
            <button key={t} className="chip" onClick={() => setP(t ? { tag: t } : {})}>{t || "all"}</button>))}
        </span>
      </div>
      <table><thead><tr><th>ID</th><th>Tag</th><th>Split</th><th>Question</th><th>Expected decisions</th><th>Author</th><th></th></tr></thead>
        <tbody>{qs.map((q) => (
          <tr key={q.id}><td>{q.id}</td><td>{q.tag}</td><td>{q.split}</td><td>{q.question}</td>
            <td>{q.gold_decision_ids.join(", ")}</td><td>{q.author}</td>
            <td><Link to={`/admin/questions/edit?id=${encodeURIComponent(q.id)}`}>Edit</Link></td></tr>
        ))}</tbody></table>
    </>
  );
}
