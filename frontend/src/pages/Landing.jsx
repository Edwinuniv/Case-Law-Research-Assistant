// The landing page at / : the idea of Verdicta told as a scroll story (question -> passages -> checked
// citations -> verified answer). It only shows; it calls no API besides /api/me (already done by App).
// The research page itself is at /research and works exactly as before.
// The example is A020 of our test set (Miller v. Alabama, answered in run 2); the fake citation is X001's.
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import "./landing.css";
import logoMark from "../assets/logo-mark.svg";
import Scales3D from "../components/Scales3D.jsx";
import statue from "../assets/statue.webp";
import chain1 from "../assets/chain1_scales.webp";
import chain2 from "../assets/chain2_page.webp";
import chain3 from "../assets/chain3_book.webp";
import chain4 from "../assets/chain4_magnifier.webp";
import chain5 from "../assets/chain5_check.webp";
import chain6 from "../assets/chain6_gavel.webp";

const QUESTION = "Can a law require life in prison without parole for a juvenile, with no chance for the judge to consider his age?";

// the chain of six images (made by Yasser): THE PAGE travels from Justice's scales to the verdict
const STEPS = [
  { img: chain1, title: "Every question is weighed.",
    text: "Your question goes on the scale. Verdicta answers only from U.S. Supreme Court opinions filed from 2000 to 2024, nothing else." },
  { img: chain2, title: "Ask in plain words.",
    text: "Type it the way you would ask a colleague.", typed: true },
  { img: chain3, title: "Read the opinions, not the internet.",
    text: "Two searches, by meaning and by keywords, run through 72,502 passages of 2,415 decisions. The best 8 go to the model, and only those." },
  { img: chain4, title: "Every quote, word for word.",
    text: "Each sentence must quote the passage it cites, word for word. A quote that is not really there is removed." },
  { img: chain5, title: "Every citation, verified.",
    text: "Six checks on every sentence. A citation that is not in CourtListener's table, or a dissent presented as the Court, never reaches you." },
  { img: chain6, title: "Verified, or it says so.",
    text: "Each citation opens the real passage. When the opinions do not support an answer, Verdicta says so instead of guessing.", cta: true },
];

const STATS = [
  { value: "0", label: "false citations shown on our test questions" },
  { value: "1.0", label: "abstention precision on the test split" },
  { value: "2,415", label: "Supreme Court decisions, 2000 to 2024" },
  { value: "6", label: "checks on every sentence before you see it" },
];

// landmark decisions of our corpus, for the moving band under the hero
const CASES = ["Bush v. Gore (2000)", "Lawrence v. Texas (2003)", "Kelo v. City of New London (2005)",
  "District of Columbia v. Heller (2008)", "Boumediene v. Bush (2008)", "Citizens United v. FEC (2010)",
  "NFIB v. Sebelius (2012)", "Shelby County v. Holder (2013)", "Riley v. California (2014)", "Obergefell v. Hodges (2015)",
  "Carpenter v. United States (2018)", "Bostock v. Clayton County (2020)", "Dobbs v. Jackson Women's Health (2022)",
  "Students for Fair Admissions v. Harvard (2023)", "Loper Bright v. Raimondo (2024)", "Trump v. United States (2024)"];

const CHECKS = [
  ["It cites what we sent", "Each sentence must point to one of the 8 passages the model received, and only those."],
  ["The quote is really there", "Its quote of five words or more is found word for word in the cited passage."],
  ["The citation exists", "Every citation must be in CourtListener's table and come from a retrieved opinion."],
  ["The case name matches", "Both parties of a case name must match the decision of the cited passage."],
  ["Numbers and dates match", "Every number and year must appear in the passage, or be the decision's own year."],
  ["A dissent is not the Court", "A sentence may not present a dissent or a concurrence as the Court's holding."],
];

const clamp = (x) => Math.min(1, Math.max(0, x));

// counts up from 0 to the number once it is on screen ("2,415", "1.0" and "0" keep their format)
function CountUp({ value }) {
  const ref = useRef(null);
  const [shown, setShown] = useState(value.replace(/[0-9]/g, "0"));
  useEffect(() => {
    const target = parseFloat(value.replace(/,/g, ""));
    const decimals = (value.split(".")[1] || "").length;
    const io = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return;
      io.disconnect();
      const t0 = performance.now();
      const tick = (t) => {
        const k = clamp((t - t0) / 1400), eased = 1 - Math.pow(1 - k, 3);
        setShown((target * eased).toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals }));
        if (k < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    }, { threshold: 0.5 });
    io.observe(ref.current);
    return () => io.disconnect();
  }, [value]);
  return <b ref={ref}>{shown}</b>;
}

export default function Landing({ info }) {
  const story = useRef(null);
  const [step, setStep] = useState(0);             // which of the 4 scenes is on screen
  const [p, setP] = useState(0);                   // progress inside that scene, 0 to 1
  const [hero, setHero] = useState(0);             // how far the hero has scrolled away, 0 to 1
  const [mouse, setMouse] = useState([0, 0]);      // mouse position over the hero, -1 to 1

  useEffect(() => {                                // the scroll position drives the story
    function onScroll() {
      setHero(clamp(window.scrollY / window.innerHeight));
      const el = story.current;
      if (!el) return;
      const total = el.offsetHeight - window.innerHeight;
      const prog = clamp(-el.getBoundingClientRect().top / total) * STEPS.length;
      const s = Math.min(STEPS.length - 1, Math.floor(prog));
      setStep(s);
      setP(clamp(prog - s));
    }
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => { window.removeEventListener("scroll", onScroll); window.removeEventListener("resize", onScroll); };
  }, []);

  useEffect(() => {                                // sections fade in when they come into view
    const seen = new IntersectionObserver((entries) => entries.forEach((e) => {
      if (e.isIntersecting) e.target.classList.add("in");
    }), { threshold: 0.2 });
    document.querySelectorAll(".lp-reveal").forEach((el) => seen.observe(el));
    return () => seen.disconnect();
  }, []);

  const typed = QUESTION.slice(0, step === 1 ? Math.round(QUESTION.length * clamp(p * 1.6)) : step > 1 ? QUESTION.length : 0);

  return (
    <div className="lp">
      <nav className="lp-nav">
        <Link to="/" className="lp-brand"><img src={logoMark} alt="" /> Verdicta</Link>
        <span className="lp-nav-links">
          <a href="#how">How it works</a>
          <Link to="/research">Research</Link>
          <Link to="/login">Admin login</Link>
        </span>
      </nav>

      <section className="lp-hero lp-hero2" onMouseMove={(e) => setMouse([e.clientX / window.innerWidth * 2 - 1, e.clientY / window.innerHeight * 2 - 1])}>
        <div className="lp-bigword" aria-hidden="true" style={{ transform: `translateX(${-hero * 18}vw)` }}>VERIFIED</div>
        <div className="lp-glow" aria-hidden="true" style={{ transform: `translate(${mouse[0] * 20}px, ${mouse[1] * 14}px)` }} />
        <div className="lp-hero-text" style={{ transform: `translateY(${-hero * 60}px)`, opacity: 1 - hero * 1.3 }}>
          <span className="lp-kicker">U.S. Supreme Court research, verified</span>
          <h1>Ask the Court.<br /><em>Hear only what it said.</em></h1>
          <p className="lp-lead">Verdicta answers questions about U.S. Supreme Court decisions and shows only sentences
            whose citations and quotes were checked against the opinions themselves.</p>
          <p className="lp-cta">
            <Link to="/research" className="lp-button">Try a question</Link>
            <a href="#how" className="lp-button ghost">See how it works ↓</a>
          </p>
          <p className="lp-coverage">{info.coverage}</p>
        </div>
        <div className="lp-statue-wrap" style={{ transform: `translate(${mouse[0] * -10}px, ${-hero * 90}px) scale(${1 + hero * 0.22})` }}>
          <img className="lp-statue" src={statue} alt="Bronze statue of Lady Justice holding the scales" />
        </div>
        <div className="lp-floats" aria-hidden="true">
          {[["lp-f1", <><span className="lp-cite-n">P1</span>Miller v. Alabama, 567 U.S. 460</>, 1.2],
            ["lp-f2", <>✓ Verified answer</>, -0.8],
            ["lp-f4", <><s>Delgado v. Oregon Fisheries Board, 597 U.S. 412</s> · removed</>, -1.1]].map(([cls, body, depth]) => (
            <span key={cls} className={`lp-float ${cls}`}
                  style={{ transform: `translate(${mouse[0] * 18 * depth}px, ${mouse[1] * 14 * depth - hero * 220 * depth}px)` }}>{body}</span>
          ))}
        </div>
        <div className="lp-scroll" aria-hidden="true"><i /></div>
      </section>

      <div className="lp-marquee" aria-label="Some of the decisions in our corpus">
        <div className="lp-track">
          {[...CASES, ...CASES].map((c, i) => <span key={i}>{c}<em>§</em></span>)}
        </div>
      </div>

      <section className="lp-story lp-chain" id="how" ref={story} style={{ height: `${STEPS.length * 100}vh` }}>
        <div className="lp-sticky">
          <div className="lp-copy">
            {STEPS.map((s, i) => (
              <div key={s.title} className={`lp-step ${i === step ? "on" : ""}`} aria-hidden={i !== step}>
                <span className="lp-num">0{i + 1} / 0{STEPS.length}</span>
                <h2>{s.title}</h2>
                <p>{s.text}</p>
                {s.typed && <p className="lp-typedq">“{typed}<i className="lp-caret" />”</p>}
                {s.cta && <Link to="/research" className="lp-button">Try a question</Link>}
              </div>
            ))}
            <div className="lp-dots">{STEPS.map((s, i) => <span key={s.title} className={i === step ? "on" : ""} />)}</div>
          </div>

          <div className="lp-chain-stage" aria-hidden="true">
            <div className="lp-chain-glow" />
            {STEPS.map((s, i) => {
              const d = step + p - i - 0.5;            // -0.5 when it arrives, 0 in the middle, +0.5 when it leaves
              const far = Math.abs(d);
              return (
                <div key={s.title} className="lp-chain-item"
                     style={{ opacity: clamp(1.25 - far * 1.6), zIndex: 10 - Math.round(far * 4),
                              transform: `translate3d(${d * 9}vw, ${d * -26}vh, 0) rotate(${d * -9}deg) scale(${1 - far * 0.28})` }}>
                  <div className="lp-float3d" style={{ animationDelay: `${-i * 1.3}s` }}>
                    <img src={s.img} alt="" loading={i < 2 ? "eager" : "lazy"} />
                    <span className="lp-shine" style={{ "--m": `url(${s.img}) center / contain no-repeat` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      <section className="lp-weigh">
        <div className="lp-weigh-copy lp-reveal">
          <span className="lp-num">THE VERIFIER</span>
          <h2>Weighed before it is shown.</h2>
          <p>The model drafts; Verdicta weighs every sentence against the passages it cites. An invented citation has no
            weight: it is not in CourtListener's table, so it is removed before you ever see it. What remains is what
            the Court actually said.</p>
          <p className="lp-weigh-hint">Drag the scale to turn it.</p>
        </div>
        <Scales3D />
      </section>

      <section className="lp-checks6 lp-reveal">
        <span className="lp-num">INSIDE THE VERIFIER</span>
        <h2>Six checks. Every sentence.</h2>
        <div className="lp-grid6">
          {CHECKS.map(([t, d], i) => (
            <div key={t} className="lp-check6" style={{ transitionDelay: `${0.15 + i * 0.12}s` }}>
              <span className="lp-check6-n">{i + 1}</span><b>{t}</b><p>{d}</p>
            </div>
          ))}
        </div>
        <p className="lp-check6-foot">A sentence that fails one check is removed, with its reason recorded. A second, separate
          checker re-reads every citation a visitor would see.</p>
      </section>

      <section className="lp-stats lp-reveal">
        {STATS.map((s) => (
          <div key={s.label}><CountUp value={s.value} /><span>{s.label}</span></div>
        ))}
      </section>

      <section className="lp-final lp-reveal">
        <h2>The model never writes a citation.</h2>
        <p>It points to numbered passages; Verdicta renders each citation from CourtListener's data, after the
          sentence has passed every check.</p>
        <Link to="/research" className="lp-button">Try a question</Link>
      </section>
    </div>
  );
}
