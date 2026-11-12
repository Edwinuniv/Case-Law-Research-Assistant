// The landing page at / : the idea of Verdicta told as a scroll story (question -> passages -> checked
// citations -> verified answer). It only shows; it calls no API besides /api/me (already done by App).
// The research page itself is at /research and works exactly as before.
// The example is A020 of our test set (Miller v. Alabama, answered in run 2); the fake citation is X001's.
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import "./landing.css";
import logoMark from "../assets/logo-mark.svg";

const QUESTION = "Can a law require life in prison without parole for a juvenile, with no chance for the judge to consider his age?";

const STEPS = [
  { title: "Ask in plain words.",
    text: "Type a question about a U.S. Supreme Court decision from 2000 to 2024, the way you would ask a colleague." },
  { title: "Read the opinions, not the internet.",
    text: "Two searches, by meaning and by keywords, run through 72,502 passages of 2,415 decisions. The best 8 passages go to the model, and only those." },
  { title: "Every citation, checked.",
    text: "Six checks on every sentence. A citation that is not in CourtListener's citation table, or a dissent presented as the Court, never reaches you." },
  { title: "Verified, or it says so.",
    text: "Each citation opens the real passage, with the quote highlighted. When the opinions do not support an answer, Verdicta says so instead of guessing." },
];

const STATS = [
  { value: "0", label: "false citations shown on our test questions" },
  { value: "1.0", label: "abstention precision on the test split" },
  { value: "2,415", label: "Supreme Court decisions, 2000 to 2024" },
  { value: "6", label: "checks on every sentence before you see it" },
];

const clamp = (x) => Math.min(1, Math.max(0, x));

export default function Landing({ info }) {
  const story = useRef(null);
  const [step, setStep] = useState(0);             // which of the 4 scenes is on screen
  const [p, setP] = useState(0);                   // progress inside that scene, 0 to 1

  useEffect(() => {                                // the scroll position drives the story
    function onScroll() {
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

  const typed = QUESTION.slice(0, Math.round(QUESTION.length * clamp(p * 1.4)));

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

      <section className="lp-hero">
        <div className="lp-hero-bg" aria-hidden="true"><span>§</span><span>“</span><span>[ ]</span><span>”</span></div>
        <svg className="lp-mark" viewBox="0 0 64 64" aria-hidden="true">
          <path className="lp-brackets" d="M15 15h-4v34h4M49 15h4v34h-4" />
          <path className="lp-check" d="M20 27l11 18L45 18" />
        </svg>
        <h1>Ask the Court.<br /><em>Hear only what it said.</em></h1>
        <p className="lp-lead">Verdicta answers questions about U.S. Supreme Court decisions and shows only sentences
          whose citations and quotes were checked against the opinions themselves.</p>
        <p className="lp-cta">
          <Link to="/research" className="lp-button">Try a question</Link>
          <a href="#how" className="lp-button ghost">See how it works ↓</a>
        </p>
        <p className="lp-coverage">{info.coverage}</p>
      </section>

      <section className="lp-story" id="how" ref={story}>
        <div className="lp-sticky">
          <div className="lp-copy">
            {STEPS.map((s, i) => (
              <div key={s.title} className={`lp-step ${i === step ? "on" : ""}`} aria-hidden={i !== step}>
                <span className="lp-num">0{i + 1}</span>
                <h2>{s.title}</h2>
                <p>{s.text}</p>
              </div>
            ))}
            <div className="lp-dots">{STEPS.map((s, i) => <span key={s.title} className={i === step ? "on" : ""} />)}</div>
          </div>

          <div className="lp-stage" aria-hidden="true">
            {/* 01: the question is typed */}
            <div className={`lp-scene ${step === 0 ? "on" : ""}`}>
              <div className="lp-search">
                <span className="lp-search-icon">?</span>
                <span className="lp-typed">{typed}<i className="lp-caret" /></span>
              </div>
              <div className={`lp-pill ${p > 0.75 ? "show" : ""}`}>Searching 72,502 passages…</div>
            </div>

            {/* 02: passages come out of the opinions; the best ones are kept */}
            <div className={`lp-scene ${step === 1 ? "on" : ""}`}>
              {["Miller v. Alabama (2012) · Majority opinion", "Miller v. Alabama (2012) · Roberts, C.J., dissenting",
                "Graham v. Florida (2010) · Majority opinion", "Montgomery v. Louisiana (2016) · Majority opinion",
                "Jones v. Mississippi (2021) · Majority opinion", "Roper v. Simmons (2005) · Majority opinion"].map((label, i) => {
                const spread = step === 1 ? clamp(p * 1.6) : 0;
                const kept = i === 0 || i === 2;
                return (
                  <div key={label} className={`lp-passage ${kept && p > 0.55 ? "kept" : ""}`}
                       style={{ transform: `translate(${(i % 2 ? 1 : -1) * spread * (40 + i * 6)}px, ${(i - 2.5) * spread * 52}px) rotate(${(1 - spread) * (i - 2.5) * 3}deg)` }}>
                    <b>P{i + 1}</b> {label}
                    <span className="lp-lines"><i /><i /><i style={{ width: "60%" }} /></span>
                  </div>
                );
              })}
            </div>

            {/* 03: the verifier keeps the real citation and removes the invented one */}
            <div className={`lp-scene ${step === 2 ? "on" : ""}`}>
              <div className="lp-draft">
                <div className="lp-sentence ok">
                  <span className="lp-lines"><i /><i style={{ width: "80%" }} /></span>
                  <span className={`lp-chip ${p > 0.2 ? "good" : ""}`}>Miller v. Alabama, 567 U.S. 460 {p > 0.2 && "✓"}</span>
                </div>
                <div className={`lp-sentence ${p > 0.45 ? "struck" : ""}`}>
                  <span className="lp-lines"><i /><i style={{ width: "70%" }} /></span>
                  <span className="lp-chip bad">Delgado v. Oregon Fisheries Board, 597 U.S. 412</span>
                  <span className={`lp-stamp ${p > 0.55 ? "show" : ""}`}>Not in CourtListener · removed</span>
                </div>
                <ul className="lp-checks">
                  {["cites a passage we sent", "quote found word for word", "citation is real and retrieved",
                    "case name matches", "numbers and dates match", "not a dissent as the Court"].map((c, i) => (
                    <li key={c} className={p > 0.1 + i * 0.12 ? "done" : ""}>{c}</li>
                  ))}
                </ul>
              </div>
            </div>

            {/* 04: the verified answer, or an honest "not supported" */}
            <div className={`lp-scene ${step === 3 ? "on" : ""}`}>
              <div className="lp-answer">
                <span className="lp-badge ok">✓ Verified answer</span>
                <span className="lp-lines"><i /><i /><i style={{ width: "55%" }} /></span>
                <span className="lp-chip good">Miller v. Alabama, 567 U.S. 460 (2012) · Majority opinion</span>
              </div>
              <div className={`lp-answer small ${p > 0.4 ? "show" : ""}`}>
                <span className="lp-badge none">⊘ Not supported by the retrieved opinions</span>
                <span className="muted">No answer is better than a wrong one.</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="lp-stats lp-reveal">
        {STATS.map((s) => (
          <div key={s.label}><b>{s.value}</b><span>{s.label}</span></div>
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
