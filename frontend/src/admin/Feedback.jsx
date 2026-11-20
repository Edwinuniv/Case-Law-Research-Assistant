// Feedback (Edwin, SPEC 11, 2026-11-20, from CedarPay's reviews): what visitors and accounts said about the answers.
// Counts, the reasons given, and the latest ratings with the question; not used by the system, read by the team.
import { Waiting, day, useLoad } from "./useLoad.jsx";

export default function Feedback() {
  const [data, error] = useLoad("/admin/feedback");
  if (!data) return <Waiting data={data} error={error} />;
  const { counts, reasons, latest } = data;
  const total = counts.helpful + counts.not_helpful;
  return (
    <>
      <h2>Answer <em>feedback</em></h2>
      <p className="ad-lead">"Was this answer helpful?" under every answer. The ratings change nothing in the system:
        they show which answers to look at. Newest first, the last 100.</p>
      <div className="ad-kpis">
        <div className="ad-kpi"><b>{total}</b><span>Ratings</span></div>
        <div className="ad-kpi ad-ok"><b>{counts.helpful}</b><span>Helpful</span>
          <small>{total ? Math.round((100 * counts.helpful) / total) : 0}% of the ratings</small></div>
        <div className="ad-kpi ad-bad"><b>{counts.not_helpful}</b><span>Not helpful</span></div>
        {Object.entries(counts.by_reason).map(([k, n]) => (
          <div className="ad-kpi" key={k}><b>{n}</b><span>{reasons[k]}</span></div>
        ))}
      </div>
      <div className="ad-table wide">
        <table>
          <thead><tr><th>When</th><th>Rating</th><th>Reason</th><th>Question</th><th>Answer</th><th>Comment</th><th>Who</th></tr></thead>
          <tbody>
            {latest.length === 0 && <tr><td colSpan={7} className="muted">No rating yet.</td></tr>}
            {latest.map((f) => (
              <tr key={f.query_id} className={f.helpful ? "" : "red"}>
                <td>{day(f.created_at)}</td>
                <td>{f.helpful ? "✓ Helpful" : "✕ Not helpful"}</td>
                <td>{f.reason ? reasons[f.reason] : "–"}</td>
                <td>{f.question}</td>
                <td><span className={`ad-status st-${f.status}`}>{f.status.replace("_", " ").toLowerCase()}</span></td>
                <td>{f.comment || "–"}</td>
                <td>{f.email || "visitor"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
