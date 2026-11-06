// Run a (before) against run b (after): worse metrics are flagged in red with text, not only colour.
import { useSearchParams } from "react-router-dom";
import { num, useLoad, Waiting } from "./useLoad.jsx";

export default function Compare() {
  const [p] = useSearchParams();
  const [d, error] = useLoad(`/admin/eval/compare?a=${p.get("a")}&b=${p.get("b")}&split=${p.get("split") ?? "test"}`);
  if (!d) return <Waiting data={d} error={error} />;
  return (
    <>
      <h2>Run {d.a} (before) vs run {d.b} (after) — {d.split || "all"} split</h2>
      <table><thead><tr><th>Metric</th><th>Run {d.a}</th><th>Run {d.b}</th></tr></thead>
        <tbody>{d.rows.map((r) => (
          <tr key={r.metric} className={r.worse ? "red" : ""}><td>{r.metric.replaceAll("_", " ")}</td>
            <td>{num(r.a)}</td><td>{num(r.b)}{r.worse && <b> ▼ worse</b>}</td></tr>
        ))}</tbody></table>
      <div className="card"><h3>Questions whose result changed ({d.flips.length})</h3>
        <table><thead><tr><th>ID</th><th>Tag</th><th>Question</th><th>Run {d.a}</th><th>Run {d.b}</th></tr></thead>
          <tbody>{d.flips.length === 0 ? <tr><td colSpan={5}>None.</td></tr> : d.flips.map((f) => (
            <tr key={f.id}><td>{f.id}</td><td>{f.tag}</td><td>{f.question}</td><td>{f.a}</td><td>{f.b}</td></tr>
          ))}</tbody></table></div>
    </>
  );
}
