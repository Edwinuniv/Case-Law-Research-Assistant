// Small SVG charts for the admin pages, in the style of the landing page (Checks6.jsx, Proof.jsx).
// They only DRAW the numbers they are given: every value comes from an /api/admin answer.
// No chart library: a ring, a half dial, stacked bars and a line are a few SVG shapes each.

export const CHECK_COLORS = ["#e879f9", "#fb7185", "#a78bfa", "#38bdf8", "#34d399", "#fb923c"];  // checks 1-6, everywhere
export const OK = "#34d399";
export const AMBER = "#fbbf24";

const isNum = (v) => typeof v === "number" && !Number.isNaN(v);
const clamp01 = (v) => Math.max(0, Math.min(1, v));

// A ring showing a share from 0 to 1 (null: an empty ring and "–").
export function Ring({ value, size = 84, stroke = 8, color = AMBER, label }) {
  const r = (size - stroke) / 2, C = 2 * Math.PI * r;
  const len = isNum(value) ? clamp01(value) * C : 0;
  return (
    <svg className="ad-ring" width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img"
         aria-label={`${label ?? ""} ${isNum(value) ? value.toFixed(2) : "no value"}`}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,.08)" strokeWidth={stroke} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round"
              transform={`rotate(-90 ${size / 2} ${size / 2})`} className="ad-arc"
              style={{ "--len": len, "--C": C }} />
      <text x="50%" y="50%" dy=".35em" textAnchor="middle" className="ad-ring-v">{isNum(value) ? value.toFixed(2) : "–"}</text>
    </svg>
  );
}

// A half dial from 0 to 1 with a white tick at the target (for example NFR3's 0.80).
export function Dial({ value, target, label }) {
  const r = 62, cx = 80, cy = 74, C = Math.PI * r;
  const at = (v, k = 1) => { const a = Math.PI * (1 - v); return [cx + r * k * Math.cos(a), cy - r * k * Math.sin(a)]; };
  const reached = isNum(value) && isNum(target) && value >= target;
  const [t1x, t1y] = isNum(target) ? at(target, 0.82) : [0, 0];
  const [t2x, t2y] = isNum(target) ? at(target, 1.18) : [0, 0];
  return (
    <svg className="ad-dial" viewBox="0 0 160 92" role="img"
         aria-label={`${label}: ${isNum(value) ? value.toFixed(2) : "no value"}${isNum(target) ? `, target ${target}` : ""}`}>
      <path d={`M${cx - r} ${cy} A${r} ${r} 0 0 1 ${cx + r} ${cy}`} fill="none" stroke="rgba(255,255,255,.08)" strokeWidth="11" strokeLinecap="round" />
      {isNum(value) && <path d={`M${cx - r} ${cy} A${r} ${r} 0 0 1 ${cx + r} ${cy}`} fill="none" stroke={reached ? OK : AMBER}
            strokeWidth="11" strokeLinecap="round" className="ad-arc" style={{ "--len": clamp01(value) * C, "--C": C }} />}
      {isNum(target) && <line x1={t1x} y1={t1y} x2={t2x} y2={t2y} stroke="#fff" strokeWidth="2" />}
      <text x={cx} y={cy - 8} textAnchor="middle" className="ad-dial-v">{isNum(value) ? value.toFixed(2) : "–"}</text>
    </svg>
  );
}

// One number in a card. tone: "ok" (green edge), "bad" (red edge) or nothing.
export function Kpi({ label, value, sub, tone, children }) {
  const shown = isNum(value) ? value.toLocaleString() : value ?? "–";
  return (
    <div className={`ad-kpi ${tone ? "ad-" + tone : ""}`}>
      {children && <div className="ad-kpi-draw">{children}</div>}
      <b className={String(shown).length > 7 ? "ad-long" : ""}>{shown}</b>
      <span>{label}</span>
      {sub && <small>{sub}</small>}
    </div>
  );
}

// Stacked bars, one bar per row of `data`; `keys` = [[field, label, colour], ...]. Height = the largest total.
export function StackedBars({ data, x, keys, height = 160 }) {
  const totals = data.map((d) => keys.reduce((s, [k]) => s + (d[k] || 0), 0));
  const max = Math.max(1, ...totals);
  const w = Math.max(data.length * 22, 220), bw = Math.min(16, (w / Math.max(1, data.length)) * 0.6);
  return (
    <div className="ad-chart">
      <svg viewBox={`0 0 ${w} ${height + 18}`} preserveAspectRatio="none" role="img"
           aria-label={`${data.length} days; largest total ${max}`}>
        {data.map((d, i) => {
          let y = height;
          const cx = (i + 0.5) * (w / data.length);
          return (
            <g key={d[x]}>
              {keys.map(([k, , c]) => {
                const h = ((d[k] || 0) / max) * (height - 6);
                y -= h;
                return h > 0 ? <rect key={k} x={cx - bw / 2} y={y} width={bw} height={h} rx="2" fill={c}><title>{`${d[x]}: ${d[k]} ${k}`}</title></rect> : null;
              })}
            </g>
          );
        })}
        <line x1="0" y1={height} x2={w} y2={height} stroke="rgba(255,255,255,.12)" />
      </svg>
      <Legend keys={keys} />
    </div>
  );
}

// Lines over the same x values; `keys` = [[field, label, colour], ...]. maxY fixes the top (e.g. 1 for a rate).
export function Lines({ data, x, keys, height = 160, maxY, marker }) {
  const w = 320;
  const top = maxY ?? Math.max(1, ...data.flatMap((d) => keys.map(([k]) => (isNum(d[k]) ? d[k] : 0))));
  const px = (i) => (data.length < 2 ? w / 2 : (i / (data.length - 1)) * (w - 12) + 6);
  const py = (v) => height - (clamp01(v / top)) * (height - 10) - 4;
  return (
    <div className="ad-chart">
      <svg viewBox={`0 0 ${w} ${height + 4}`} role="img" aria-label={`${keys.map((k) => k[1]).join(", ")}; top ${top}`}>
        {[0, 0.5, 1].map((f) => (                              // grid lines with their values (0, half, top)
          <g key={f}>
            <line x1="0" y1={py(f * top)} x2={w} y2={py(f * top)} stroke="rgba(255,255,255,.07)" />
            <text x="2" y={f === 1 ? py(top) + 10 : py(f * top) - 3} className="ad-axis">{+(f * top).toFixed(2)}</text>
          </g>
        ))}
        {isNum(marker) && data.length > 0 && (() => {           // a vertical line at one x value (the current tau)
          const i = data.findIndex((d) => Math.abs(d[x] - marker) < 0.011);
          return i >= 0 ? <line x1={px(i)} y1="0" x2={px(i)} y2={height} stroke="#fff" strokeDasharray="3 3" opacity=".6" /> : null;
        })()}
        {keys.map(([k, , c]) => {
          const pts = data.map((d, i) => (isNum(d[k]) ? `${px(i)},${py(d[k])}` : null)).filter(Boolean);
          return pts.length ? (
            <g key={k}>
              <polyline points={pts.join(" ")} fill="none" stroke={c} strokeWidth="2.2" strokeLinejoin="round" strokeLinecap="round" />
              {data.map((d, i) => isNum(d[k]) && data.length <= 12 &&      // a dot per value when there are few
                <circle key={i} cx={px(i)} cy={py(d[k])} r="3.5" fill={c}><title>{`${d[x]}: ${d[k]}`}</title></circle>)}
            </g>) : null;
        })}
      </svg>
      <Legend keys={keys} />
    </div>
  );
}

export function Legend({ keys }) {
  return (
    <ul className="ad-legend">
      {keys.map(([k, label, c]) => <li key={k}><i style={{ background: c }} />{label}</li>)}
    </ul>
  );
}

// The metrics that are shares or rates from 0 to 1 (the others are counts or times): only these get bars.
export const RATE_METRICS = new Set(["recall@1", "recall@5", "recall@10", "mrr@10", "abstention_precision", "abstention_recall",
  "false_citation_rate", "groundedness_judge", "groundedness_lexical", "adversarial_abstention_rate"]);

// Two values of the same metric side by side (before / after), as two thin bars on a 0-1 scale.
export function PairBars({ a, b, worse }) {
  const bar = (v, cls) => <i className={cls} style={{ width: `${isNum(v) ? clamp01(v) * 100 : 0}%` }} />;
  return (
    <span className={`ad-pair ${worse ? "ad-worse" : ""}`} aria-hidden="true">
      {bar(a, "ad-pair-a")}{bar(b, "ad-pair-b")}
    </span>
  );
}

// The status of an answer or a test question: icon AND words, never colour alone (SR32).
const STATUS = {
  ANSWERED: ["✓", "Answered"], LOW_CONFIDENCE: ["⚠", "Low confidence"],
  NOT_SUPPORTED: ["⊘", "Not supported"], ERROR: ["✕", "Error"],
};
export function StatusBadge({ status }) {
  const [icon, text] = STATUS[status] || ["?", status];
  return <span className={`ad-status st-${status}`}><span aria-hidden="true">{icon}</span> {text}</span>;
}
