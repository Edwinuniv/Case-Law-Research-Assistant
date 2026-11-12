// "Six checks. Every sentence." on the landing page, with the real numbers of run 2
// (eval/runs/eval_run2_reverified.json): the model drafted 99 sentences for the 85 questions; 82 passed every
// check, 17 were removed. A big ring shows the 99 sentences, coloured by the check that removed them; each
// check has its own colour and a small ring with its share of the 17. The rings draw themselves when the
// section comes into view.
import { useEffect, useRef, useState } from "react";
import "./checks6.css";

const DRAFTED = 99, KEPT = 82;
// removed: sentences this check removed in run 2 (a sentence can fail more than one check)
const CHECKS = [
  { title: "It cites what we sent", text: "Each sentence must point to one of the 8 passages the model received, and only those.", color: "#e879f9", removed: 1 },
  { title: "The quote is really there", text: "Its quote of five words or more is found word for word in the cited passage.", color: "#fb7185", removed: 8 },
  { title: "The citation exists", text: "Every citation must be in CourtListener's table and come from a retrieved opinion.", color: "#a78bfa", removed: 0 },
  { title: "The case name matches", text: "Both parties of a case name must match the decision of the cited passage.", color: "#38bdf8", removed: 1 },
  { title: "Numbers and dates match", text: "Every number and year must appear in the passage, or be the decision's own year.", color: "#34d399", removed: 0 },
  { title: "A dissent is not the Court", text: "A sentence may not present a dissent or a concurrence as the Court's holding.", color: "#fb923c", removed: 8 },
];
const REMOVED = CHECKS.reduce((s, c) => s + c.removed, 0);   // 18 failures for 17 sentences: one failed two checks

function Ring({ size, stroke, parts, track = "rgba(255,255,255,.08)", gap = 0, children }) {
  const r = (size - stroke) / 2, C = 2 * Math.PI * r;
  let start = 0;
  return (
    <svg className="c6-ring" width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={track} strokeWidth={stroke} />
      {parts.filter((p) => p.share > 0).map((p, k) => {
        const len = Math.max(0, p.share * C - gap);
        const el = (
          <circle key={k} cx={size / 2} cy={size / 2} r={r} fill="none" stroke={p.color} strokeWidth={stroke}
                  strokeLinecap={gap ? "butt" : "round"} transform={`rotate(${-90 + (start / C) * 360} ${size / 2} ${size / 2})`}
                  style={{ "--len": len, "--C": C, transitionDelay: `${p.delay ?? 0}s` }} className="c6-arc" />
        );
        start += p.share * C;
        return el;
      })}
      {children}
    </svg>
  );
}

export default function Checks6() {
  const ref = useRef(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setInView(true); io.disconnect(); } }, { threshold: 0.25 });
    io.observe(ref.current);
    return () => io.disconnect();
  }, []);

  // the big ring: kept sentences, then the removed ones, one arc per check
  const big = [{ color: "url(#c6-kept)", share: KEPT / DRAFTED, delay: 0.1 },
    ...CHECKS.filter((c) => c.removed).map((c, k) => ({ color: c.color, share: (c.removed / REMOVED) * ((DRAFTED - KEPT) / DRAFTED), delay: 1.1 + k * 0.15 }))];

  return (
    <section className={`c6 ${inView ? "in" : ""}`} ref={ref} id="how">
      <span className="c6-kicker">INSIDE THE VERIFIER</span>
      <h2>Six checks. <em>Every sentence.</em></h2>
      <p className="c6-lead">A sentence that fails one check is removed, with its reason recorded. These are the real numbers
        of our final evaluation run: 85 questions, every sentence the model drafted.</p>

      <div className="c6-top">
        <div className="c6-big">
          <Ring size={260} stroke={22} parts={big} gap={3}>
            <defs>
              <linearGradient id="c6-kept" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#fde68a" /><stop offset="1" stopColor="#f59e0b" /></linearGradient>
            </defs>
          </Ring>
          <div className="c6-big-label"><b>{KEPT}</b><span>of {DRAFTED} sentences<br />passed all six</span></div>
        </div>
        <ul className="c6-legend">
          <li><i style={{ background: "linear-gradient(135deg,#fde68a,#f59e0b)" }} /><b>{KEPT}</b> kept, shown to the visitor</li>
          {CHECKS.filter((c) => c.removed).map((c) => (
            <li key={c.title}><i style={{ background: c.color }} /><b>{c.removed}</b> removed by “{c.title}”</li>
          ))}
          <li className="c6-zero">0 false citations shown, on every split</li>
        </ul>
      </div>

      <div className="c6-grid">
        {CHECKS.map((c, i) => (
          <article key={c.title} className="c6-card" style={{ "--c": c.color, transitionDelay: `${0.2 + i * 0.1}s` }}>
            <div className="c6-card-ring">
              <Ring size={64} stroke={5} parts={[{ color: c.color, share: c.removed / (DRAFTED - KEPT), delay: 0.6 + i * 0.1 }]}>
                <text x="32" y="38" textAnchor="middle" className="c6-n">{i + 1}</text>
              </Ring>
            </div>
            <b>{c.title}</b>
            <p>{c.text}</p>
            <div className="c6-meter">
              <span className="c6-dots" aria-hidden="true">
                {Array.from({ length: DRAFTED - KEPT }, (_, k) => <i key={k} className={k < c.removed ? "on" : ""} style={{ transitionDelay: `${0.9 + k * 0.04}s` }} />)}
              </span>
              <small>{c.removed ? `removed ${c.removed} of the 17` : "removed none in run 2"}</small>
            </div>
          </article>
        ))}
      </div>
      <p className="c6-foot">A second, separate checker re-reads every citation a visitor would see. One removed sentence failed
        two checks, so the six counts add up to 18.</p>
    </section>
  );
}
