// Run a (before) against run b (after): worse metrics are flagged in red WITH text ("▼ worse"), not only colour.
// Every number comes from GET /api/admin/eval/compare. A share or rate (RATE_METRICS) also gets two thin bars.
import { useSearchParams } from "react-router-dom";
import { PairBars, RATE_METRICS, StatusBadge } from "./charts.jsx";
import { num, useLoad, Waiting } from "./useLoad.jsx";

export default function Compare() {
  const [p] = useSearchParams();
  const [d, error] = useLoad(`/admin/eval/compare?a=${p.get("a")}&b=${p.get("b")}&split=${p.get("split") ?? "tune"}`);
  if (!d) return <Waiting data={d} error={error} />;
  const worse = d.rows.filter((r) => r.worse).length;
  return (
    <>
      <h2>Run {d.a} <em>vs</em> run {d.b}</h2>
      <p className="ad-lead">Run {d.a} is before, run {d.b} after, on the {d.split || "whole"} split. {worse} metric(s) got worse.
        Bars: grey = before, amber = after (red when worse).</p>
      <div className="ad-table">
          <table><thead><tr><th>Metric</th><th>Run {d.a}</th><th>Run {d.b}</th></tr></thead>
            <tbody>{d.rows.map((r) => (
              <tr key={r.metric} className={r.worse ? "red" : ""}><td>{r.metric.replaceAll("_", " ")}</td>
                <td>{num(r.a)}</td>
                <td>{num(r.b)}{r.worse && <b> ▼ worse</b>}{RATE_METRICS.has(r.metric) && <PairBars a={r.a} b={r.b} worse={r.worse} />}</td></tr>
            ))}</tbody></table>
      </div>
      <div className="ad-card"><h3>Questions whose result changed ({d.flips.length})</h3>
        <div className="ad-table wide"><table><thead><tr><th>ID</th><th>Tag</th><th>Question</th><th>Run {d.a}</th><th>Run {d.b}</th></tr></thead>
          <tbody>{d.flips.length === 0 ? <tr><td colSpan={5}>None.</td></tr> : d.flips.map((f) => (
            <tr key={f.id}><td><b>{f.id}</b></td><td>{f.tag}</td><td>{f.question}</td>
              <td><StatusBadge status={f.a} /></td><td><StatusBadge status={f.b} /></td></tr>
          ))}</tbody></table></div></div>
    </>
  );
}
