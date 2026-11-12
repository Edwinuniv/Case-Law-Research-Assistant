// The landing page at / : a film at the top that plays by itself (the statue, then the chain of six 3D
// images: scales -> page -> books -> magnifying glass -> check -> gavel), then the 3D scale, the six checks,
// the numbers and "Try a question". It only shows; it calls no API besides /api/me (already done by App).
// The research page itself is at /research and works exactly as before.
// The example is A020 of our test set (Miller v. Alabama, answered in run 2); the fake citation is X001's.
import { useEffect } from "react";
import { Link } from "react-router-dom";
import "./landing.css";
import logoMark from "../assets/logo-mark.svg";
import Scales3D from "../components/Scales3D.jsx";
import Story3D from "../components/Story3D.jsx";
import Checks6 from "../components/Checks6.jsx";
import Proof from "../components/Proof.jsx";
import statue from "../assets/statue.webp";


// the chain of six images (made by Yasser): THE PAGE travels from Justice's scales to the verdict
const STEPS = [
  { word: "WEIGHED", title: "Every question is weighed.",
    text: "Your question goes on the scale. Verdicta answers only from U.S. Supreme Court opinions filed from 2000 to 2024, nothing else." },
  { word: "ASK", title: "Ask in plain words.",
    text: "Type it the way you would ask a colleague: \"Can a law require life without parole for a juvenile, with no chance for the judge to consider his age?\"" },
  { word: "READ", title: "Read the opinions, not the internet.",
    text: "Two searches, by meaning and by keywords, run through 72,502 passages of 2,415 decisions. The best 8 go to the model, and only those." },
  { word: "QUOTED", title: "Every quote, word for word.",
    text: "Each sentence must quote the passage it cites, word for word. A quote that is not really there is removed." },
  { word: "CHECKED", title: "Every citation, verified.",
    text: "Six checks on every sentence. A citation that is not in CourtListener's table, or a dissent presented as the Court, never reaches you." },
  { word: "VERDICT", title: "Verified, or it says so.",
    text: "Each citation opens the real passage. When the opinions do not support an answer, Verdicta says so instead of guessing.", cta: true },
];

// landmark decisions of our corpus, for the moving band under the hero
const CASES = ["Bush v. Gore (2000)", "Lawrence v. Texas (2003)", "Kelo v. City of New London (2005)",
  "District of Columbia v. Heller (2008)", "Boumediene v. Bush (2008)", "Citizens United v. FEC (2010)",
  "NFIB v. Sebelius (2012)", "Shelby County v. Holder (2013)", "Riley v. California (2014)", "Obergefell v. Hodges (2015)",
  "Carpenter v. United States (2018)", "Bostock v. Clayton County (2020)", "Dobbs v. Jackson Women's Health (2022)",
  "Students for Fair Admissions v. Harvard (2023)", "Loper Bright v. Raimondo (2024)", "Trump v. United States (2024)"];

export default function Landing({ info }) {
  useEffect(() => {                                // sections fade in when they come into view
    const seen = new IntersectionObserver((entries) => entries.forEach((e) => {
      if (e.isIntersecting) e.target.classList.add("in");
    }), { threshold: 0.2 });
    document.querySelectorAll(".lp-reveal").forEach((el) => seen.observe(el));
    return () => seen.disconnect();
  }, []);



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

      <Story3D statue={statue} coverage={info.coverage} scenes={[
        { title: "Ask the Court. Hear only what it said.", accent: [3, 4, 5, 6],
          text: "Verdicta answers questions about U.S. Supreme Court decisions and shows only sentences whose citations and quotes were checked against the opinions themselves." },
        STEPS[0], STEPS[2], STEPS[3], STEPS[4]]} />

      <div className="lp-marquee" aria-label="Some of the decisions in our corpus">
        <div className="lp-track">
          {[...CASES, ...CASES].map((c, i) => <span key={i}>{c}<em>§</em></span>)}
        </div>
      </div>


      <section className="lp-weigh" id="weigh">
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

      <Checks6 />

      <Proof />
    </div>
  );
}
