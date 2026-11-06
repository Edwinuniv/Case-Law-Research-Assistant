// Analytics (SR42): queries per day by result, response time (p50, p95), failure rate, date filter,
// and the questions it could not answer. Charts drawn with chart.js.
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import Chart from "chart.js/auto";
import { day, useLoad, Waiting } from "./useLoad.js";

function ChartBox({ title, config }) {          // one chart; redrawn when its data changes
  const canvas = useRef(null);
  useEffect(() => {
    const chart = new Chart(canvas.current, config);
    return () => chart.destroy();
  }, [config]);
  return <div className="card"><h3>{title}</h3><canvas ref={canvas} /></div>;
}

export default function Analytics() {
  const [range, setRange] = useState({ start: "", end: "" });
  const [query, setQuery] = useState("");
  const [d, error] = useLoad(`/admin/analytics${query}`);
  useEffect(() => { if (d && !range.start) setRange({ start: d.start, end: d.end }); }, [d, range.start]);
  if (!d) return <Waiting data={d} error={error} />;

  const L = d.days.map((x) => x.day);
  const series = (label, key, color) => ({ label, data: d.days.map((x) => x[key]), backgroundColor: color, borderColor: color });
  const results = { type: "bar", data: { labels: L, datasets: [series("answered", "answered", "#2f7d3b"),
    series("low confidence", "low", "#c58b00"), series("not supported", "not_supported", "#7a8594"),
    series("error", "errors", "#b3342b")] }, options: { scales: { x: { stacked: true }, y: { stacked: true } } } };
  const times = { type: "line", data: { labels: L, datasets: [series("median (p50)", "p50", "#1f3a5f"), series("p95", "p95", "#c58b00")] } };
  const failures = { type: "line", data: { labels: L, datasets: [series("share of queries with an error", "failure_rate", "#b3342b")] },
    options: { scales: { y: { min: 0, max: 1 } } } };

  return (
    <>
      <h2>Analytics</h2>
      <form className="card" onSubmit={(e) => { e.preventDefault(); setQuery(`?start=${range.start}&end=${range.end}`); }}>
        From <input type="date" value={range.start} onChange={(e) => setRange({ ...range, start: e.target.value })} /> to{" "}
        <input type="date" value={range.end} onChange={(e) => setRange({ ...range, end: e.target.value })} />{" "}
        <button className="light">Apply</button>
      </form>
      <div className="two">
        <ChartBox title="Queries per day, by result" config={results} />
        <ChartBox title="Response time (ms)" config={times} />
      </div>
      <div className="two">
        <ChartBox title="Failure rate (errors)" config={failures} />
        <div className="card"><h3>Questions it could not answer</h3>
          <ul>{d.unanswered.length === 0 ? <li>None in this period.</li> : d.unanswered.map((u, i) => (
            <li key={i}>{u.question} <span className="muted">{day(u.created_at).slice(5, 10)} · {u.reason}</span></li>))}</ul>
          <Link to="/admin/abstentions">Review them</Link></div>
      </div>
    </>
  );
}
