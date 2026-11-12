// The numbers band and the closing call of the landing page.
// Numbers from the saved TEST report (eval/runs/test_split_run2_reverified_2026-11-09.txt, tau 0.20):
// 23 citations shown, 0 false; abstention precision 1.0, recall 0.8 (target >= 0.80, NFR3). Corpus: 2,415
// decisions filed 2000-2024, 72,502 passages. Each number has a small drawing that animates once in view.
// The closing part shows what "the model never writes a citation" means: the model writes a passage number
// [P3]; Verdicta turns it into the citation from CourtListener's table.
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import "./proof.css";

const clamp = (x) => Math.min(1, Math.max(0, x));
const COLORS = ["#e879f9", "#fb7185", "#a78bfa", "#38bdf8", "#34d399", "#fb923c"];   // the six checks' colours

function useInView(threshold = 0.35) {
  const ref = useRef(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setInView(true); io.disconnect(); } }, { threshold });
    io.observe(ref.current);
    return () => io.disconnect();
  }, [threshold]);
  return [ref, inView];
}

// counts up from 0 to the number ("2,415", "1.0" and "0" keep their format)
function CountUp({ value, go }) {
  const [shown, setShown] = useState(value.replace(/[0-9]/g, "0"));
  useEffect(() => {
    if (!go) return;
    const target = parseFloat(value.replace(/,/g, "")), decimals = (value.split(".")[1] || "").length;
    const t0 = performance.now();
    let raf;
    const tick = (t) => {
      const k = clamp((t - t0) / 1400), eased = 1 - Math.pow(1 - k, 3);
      setShown((target * eased).toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals }));
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [go, value]);
  return <b className="pf-num">{shown}</b>;
}

const Citations = () => (                          // 23 citations shown on TEST, all real
  <div className="pf-dots23" aria-hidden="true">
    {Array.from({ length: 23 }, (_, k) => <i key={k} style={{ transitionDelay: `${0.3 + k * 0.05}s` }} />)}
  </div>
);

const Gauge = () => {                              // a half dial: 1.0 reached, the 0.80 target (NFR3) marked by a white tick
  const r = 70, C = Math.PI * r;
  const at = (v) => { const a = Math.PI * (1 - v); return [90 + r * Math.cos(a), 84 - r * Math.sin(a)]; };
  const [tx, ty] = at(0.8), [ox, oy] = at(0.8).map((c, i) => (c - [90, 84][i]) * 1.2 + [90, 84][i]);
  return (
    <svg className="pf-gauge" viewBox="0 0 180 96" aria-hidden="true">
      <defs><linearGradient id="pf-g" x1="0" x2="1"><stop offset="0" stopColor="#f59e0b" /><stop offset="1" stopColor="#34d399" /></linearGradient></defs>
      <path d="M20 84 A70 70 0 0 1 160 84" fill="none" stroke="rgba(255,255,255,.08)" strokeWidth="12" strokeLinecap="round" />
      <path d="M20 84 A70 70 0 0 1 160 84" fill="none" stroke="url(#pf-g)" strokeWidth="12" strokeLinecap="round"
            className="pf-gauge-arc" style={{ "--C": C }} />
      <line x1={tx} y1={ty} x2={ox} y2={oy} stroke="#fff" strokeWidth="2" />
    </svg>
  );
};

const Years = () => (                              // the 25 years of the corpus, lighting up in turn
  <div className="pf-years" aria-hidden="true">
    <div className="pf-ticks">{Array.from({ length: 25 }, (_, k) => <i key={k} style={{ transitionDelay: `${0.3 + k * 0.04}s` }} />)}</div>
    <div className="pf-years-l"><span>2000</span><span>2024</span></div>
  </div>
);

const Six = () => (                                // the six checks, in their colours, on a ring
  <svg className="pf-six" viewBox="0 0 100 100" aria-hidden="true">
    <circle cx="50" cy="50" r="34" fill="none" stroke="rgba(255,255,255,.08)" strokeWidth="1.5" />
    {COLORS.map((c, k) => {
      const a = (k / 6) * Math.PI * 2 - Math.PI / 2;
      return <circle key={c} cx={50 + 34 * Math.cos(a)} cy={50 + 34 * Math.sin(a)} r="7" fill={c}
                     style={{ transitionDelay: `${0.3 + k * 0.12}s`, filter: `drop-shadow(0 0 6px ${c})` }} />;
    })}
  </svg>
);

const STATS = [
  { value: "0", label: "false citations shown", sub: "0 of the 23 citations shown on the test split", Draw: Citations },
  { value: "1.0", label: "abstention precision", sub: "right each time it said “not supported” · recall 0.8 · white tick: target 0.80", Draw: Gauge },
  { value: "2,415", label: "Supreme Court decisions", sub: "U.S. Supreme Court opinions filed 2000 to 2024 · 72,502 passages", Draw: Years },
  { value: "6", label: "checks on every sentence", sub: "before a visitor sees it", Draw: Six },
];

export default function Proof() {
  const [band, bandIn] = useInView();
  const [cta, ctaIn] = useInView(0.3);
  return (
    <>
      <section className={`pf ${bandIn ? "in" : ""}`} ref={band} aria-label="Results on our test questions">
        {STATS.map(({ value, label, sub, Draw }, i) => (
          <div key={label} className="pf-card" style={{ transitionDelay: `${i * 0.1}s` }}>
            <div className="pf-draw"><Draw /></div>
            <CountUp value={value} go={bandIn} />
            <span className="pf-label">{label}</span>
            <small className="pf-sub">{sub}</small>
          </div>
        ))}
      </section>

      <section className={`pf-final ${ctaIn ? "in" : ""}`} ref={cta}>
        <h2>The model never writes <em>a citation.</em></h2>
        <p>It points to a numbered passage. Verdicta writes the citation itself, from CourtListener's table, and only
          after the sentence has passed every check.</p>
        <div className="pf-demo" aria-label="Example: the model writes P3, Verdicta shows Miller v. Alabama, 567 U.S. 460">
          <span className="pf-demo-tag">the model writes</span>
          <p className="pf-demo-line">A law may not require life without parole for every juvenile, with no chance for the
            judge to consider age.{" "}
            <span className="pf-swap">
              <span className="pf-p3">[P3]</span>
              <span className="pf-cite"><i>✓</i> Miller v. Alabama, 567 U.S. 460</span>
            </span>
          </p>
          <span className="pf-demo-tag right">Verdicta shows</span>
        </div>
        <Link to="/research" className="lp-button pf-button">Try a question</Link>
        <p className="pf-legal">This is a research aid, not legal advice. · Data: CourtListener (Free Law Project), public domain.</p>
        <nav className="pf-links" aria-label="Site information">
          <Link to="/privacy">Privacy</Link><Link to="/terms">Terms of use</Link>
          <Link to="/sources">Sources &amp; licences</Link><Link to="/contact">Contact</Link>
        </nav>
      </section>
    </>
  );
}
