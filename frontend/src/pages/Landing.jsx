// The landing page at / : the statue, then the idea of Verdicta told by a chain of six 3D images, each on
// its own screen (scales -> page -> books -> magnifying glass -> check -> gavel). It only shows; it calls no API besides /api/me (already done by App).
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
  { img: chain1, word: "WEIGHED", title: "Every question is weighed.",
    text: "Your question goes on the scale. Verdicta answers only from U.S. Supreme Court opinions filed from 2000 to 2024, nothing else." },
  { img: chain2, word: "ASK", title: "Ask in plain words.",
    text: "Type it the way you would ask a colleague.", typed: true },
  { img: chain3, word: "READ", title: "Read the opinions, not the internet.",
    text: "Two searches, by meaning and by keywords, run through 72,502 passages of 2,415 decisions. The best 8 go to the model, and only those." },
  { img: chain4, word: "QUOTED", title: "Every quote, word for word.",
    text: "Each sentence must quote the passage it cites, word for word. A quote that is not really there is removed." },
  { img: chain5, word: "CHECKED", title: "Every citation, verified.",
    text: "Six checks on every sentence. A citation that is not in CourtListener's table, or a dissent presented as the Court, never reaches you." },
  { img: chain6, word: "VERDICT", title: "Verified, or it says so.",
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
// how far a section has travelled through the screen: 0 when its top reaches the bottom of the window,
// 0.5 when it is centred, 1 when its bottom leaves the top
function useTravel(ref) {
  const [r, setR] = useState(0);
  useEffect(() => {
    let raf = 0;
    const measure = () => {
      raf = 0;
      const el = ref.current; if (!el) return;
      const box = el.getBoundingClientRect(), vh = window.innerHeight;
      setR(clamp((vh - box.top) / (vh + box.height)));
    };
    const onScroll = () => { if (!raf) raf = requestAnimationFrame(measure); };
    measure();
    window.addEventListener("scroll", onScroll, { passive: true }); window.addEventListener("resize", onScroll);
    return () => { window.removeEventListener("scroll", onScroll); window.removeEventListener("resize", onScroll); cancelAnimationFrame(raf); };
  }, [ref]);
  return r;
}

const ease = (x) => 1 - Math.pow(1 - clamp(x), 3);

// one chapter of the chain: its own full screen, its image flies in, floats, then flies out toward the next one
function Chapter({ s, i, count }) {
  const ref = useRef(null);
  const r = useTravel(ref);
  const dir = i % 2 ? -1 : 1;                        // image on the right, then on the left, and so on
  const enter = ease((r - 0.08) / 0.36), leave = ease((r - 0.62) / 0.34);
  const typed = s.typed ? QUESTION.slice(0, Math.round(QUESTION.length * clamp((r - 0.25) / 0.3))) : "";
  return (
    <section ref={ref} className={`lp-ch ${dir < 0 ? "flip" : ""}`} data-ch={i}>
      <div className="lp-ch-word" aria-hidden="true" style={{ transform: `translateX(${(0.5 - r) * 45 * dir}vw)` }}>{s.word}</div>
      <div className="lp-ch-text" style={{ opacity: enter * (1 - leave), transform: `translateY(${(1 - enter) * 60 - leave * 80}px)` }}>
        <span className="lp-ch-n">{i + 1}.</span>
        <span className="lp-num">{String(i + 1).padStart(2, "0")} / {String(count).padStart(2, "0")}</span>
        <h2>{s.title}</h2>
        <p>{s.text}</p>
        {s.typed && <p className="lp-typedq">“{typed}<i className="lp-caret" />”</p>}
        {s.cta && <Link to="/research" className="lp-button">Try a question</Link>}
      </div>
      <div className="lp-ch-img" aria-hidden="true"
           style={{ opacity: clamp(enter * 1.2) * (1 - leave * 0.85),
                    transform: `translate3d(${dir * (1 - enter) * 38}vw, ${(1 - enter) * 14 - leave * 34}vh, 0) rotate(${dir * ((1 - enter) * 22 - leave * 12)}deg) scale(${0.72 + enter * 0.28 + leave * 0.18})` }}>
        <div className="lp-ch-glow" />
        <div className="lp-float3d" style={{ animationDelay: `${-i * 1.3}s` }}>
          <img src={s.img} alt="" loading={i < 2 ? "eager" : "lazy"} />
          <span className="lp-shine" style={{ "--m": `url(${s.img}) center / contain no-repeat` }} />
        </div>
      </div>
    </section>
  );
}

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
  const [hero, setHero] = useState(0);             // how far the hero has scrolled away, 0 to 1
  const [mouse, setMouse] = useState([0, 0]);      // mouse position over the hero, -1 to 1

  useEffect(() => {                                // the hero zooms and fades as it scrolls away
    const onScroll = () => setHero(clamp(window.scrollY / window.innerHeight));
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {                                // sections fade in when they come into view
    const seen = new IntersectionObserver((entries) => entries.forEach((e) => {
      if (e.isIntersecting) e.target.classList.add("in");
    }), { threshold: 0.2 });
    document.querySelectorAll(".lp-reveal").forEach((el) => seen.observe(el));
    return () => seen.disconnect();
  }, []);

  // "Watch the story": scrolls through every chapter by itself, like a film; any wheel, touch or key stops it
  const [watching, setWatching] = useState(false);
  useEffect(() => {
    if (!watching) return;
    let stop = false, raf = 0, timer = 0;
    const cancel = () => { stop = true; setWatching(false); };
    const glide = (to, ms, done) => {
      const from = window.scrollY, t0 = performance.now();
      const step = (t) => {
        if (stop) return;
        const k = clamp((t - t0) / ms), e = k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
        window.scrollTo(0, from + (to - from) * e);
        if (k < 1) raf = requestAnimationFrame(step); else done();
      };
      raf = requestAnimationFrame(step);
    };
    const stops = [...document.querySelectorAll(".lp-ch")].map((el) => el.offsetTop);
    let n = 0;
    const next = () => {
      if (stop || n >= stops.length) { setWatching(false); return; }
      glide(stops[n++], 2200, () => { timer = setTimeout(next, 2600); });
    };
    next();
    ["wheel", "touchstart", "keydown"].forEach((ev) => window.addEventListener(ev, cancel, { passive: true }));
    return () => { stop = true; cancelAnimationFrame(raf); clearTimeout(timer);
      ["wheel", "touchstart", "keydown"].forEach((ev) => window.removeEventListener(ev, cancel)); };
  }, [watching]);

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
            <button type="button" className="lp-button ghost" onClick={() => setWatching(true)}>▶ Watch the story</button>
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

      <div id="how">
        {STEPS.map((st, i) => <Chapter key={st.title} s={st} i={i} count={STEPS.length} />)}
      </div>

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
