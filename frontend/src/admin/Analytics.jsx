// Analytics (SR42): queries per day by result, response time (p50, p95), failure rate, date filter,
// and the questions it could not answer. Every number comes from GET /api/admin/analytics; the totals at the
// top are sums of its per-day counts. Drawn with the small SVG charts of charts.jsx (no chart library).
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AMBER, Kpi, Lines, OK, StackedBars } from "./charts.jsx";
import { day, useLoad, Waiting } from "./useLoad.jsx";

const RESULTS = [["answered", "answered", OK], ["low", "low confidence", AMBER],
  ["not_supported", "not supported", "#94a3b8"], ["errors", "error", "#f87171"]];

export default function Analytics() {
  const [range, setRange] = useState({ start: "", end: "" });
  const [query, setQuery] = useState("");
  const [d, error] = useLoad(`/admin/analytics${query}`);
  useEffect(() => { if (d && !range.start) setRange({ start: d.start, end: d.end }); }, [d, range.start]);
  if (!d) return <Waiting data={d} error={error} />;

  const sum = (k) => d.days.reduce((s, x) => s + (x[k] || 0), 0);
  const total = sum("n");

  return (
    <>
      <h2>Analytics</h2>
      <p className="ad-lead">Questions asked on the website from {d.start} to {d.end}, by day.</p>
      <form className="ad-card ad-form" onSubmit={(e) => { e.preventDefault(); setQuery(`?start=${range.start}&end=${range.end}`); }}>
        <label className="ad-field">From<input type="date" value={range.start} onChange={(e) => setRange({ ...range, start: e.target.value })} /></label>
        <label className="ad-field">To<input type="date" value={range.end} onChange={(e) => setRange({ ...range, end: e.target.value })} /></label>
        <button className="light">Apply</button>
      </form>

      <div className="ad-kpis">
        <Kpi label="questions" value={total} />
        {RESULTS.map(([k, label]) => <Kpi key={k} label={label} value={sum(k)}
                                          tone={k === "errors" ? (sum(k) ? "bad" : "ok") : undefined} />)}
      </div>

      {d.days.length === 0 ? <div className="ad-card">No question in this period.</div> : (
        <>
          <div className="ad-two">
            <div className="ad-card"><h3>Questions per day, by result</h3>
              <StackedBars data={d.days} x="day" keys={RESULTS} />
              <p className="muted">{d.days[0].day} to {d.days[d.days.length - 1].day}</p></div>
            <div className="ad-card"><h3>Response time (ms)</h3>
              <Lines data={d.days} x="day" keys={[["p50", "median (p50)", "#38bdf8"], ["p95", "p95", AMBER]]} /></div>
          </div>
          <div className="ad-two">
            <div className="ad-card"><h3>Failure rate (share of questions with an error)</h3>
              <Lines data={d.days} x="day" maxY={1} keys={[["failure_rate", "failure rate", "#f87171"]]} /></div>
            <div className="ad-card"><h3>Questions it could not answer</h3>
              <ul>{d.unanswered.length === 0 ? <li>None in this period.</li> : d.unanswered.map((u, i) => (
                <li key={i}>{u.question} <span className="muted">{day(u.created_at).slice(5, 10)} · {u.reason}</span></li>))}</ul>
              <Link to="/admin/abstentions">Review them →</Link></div>
          </div>
        </>
      )}
    </>
  );
}
