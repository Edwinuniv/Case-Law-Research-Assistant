// A guided tour of the research page (Edwin, SPEC 11, 2026-11-20, from CedarPay's tutorial; for NFR9 usability).
// One part at a time is lit (a hole in a dark veil) with a card next to it: Next / Back / Skip, Escape closes.
// A step whose part is not on the screen (a phone's closed sidebar) is skipped. Seen once per browser (localStorage);
// Settings > "Take the tour" opens /research?tour=1 to see it again. Nothing is sent to the server.
import { useCallback, useEffect, useState } from "react";
import "./tour.css";

const KEY = "verdicta-tour-done";
const STEPS = [
  { at: ".rs-box", title: "Ask here", text: "Type a question about a U.S. Supreme Court decision from 2000 to 2024, in your own words. Enter sends it." },
  { at: ".rs-examples", title: "Or start with an example", text: "These answers were made once and checked: they open at once." },
  { at: ".rs-side", title: "Your questions", text: "Each question appears here. Create a free account to keep them and find them again." },
  { at: ".ts-btn", title: "Settings", text: "Dark or light: choose how Verdicta looks. You can take this tour again from here." },
  { title: "How to read an answer", list: [
    ["✓ Verified answer", "every sentence was checked against the passage it cites."],
    ["⚠ Low confidence", "the support is partial: read the passages before relying on it."],
    ["⊘ Not supported", "the opinions we searched do not answer it, so Verdicta does not guess."],
    ["Gold citation", "click it to read the exact passage, with the quoted words highlighted."],
    ["⤓ PDF and 👍 / 👎", "keep the answer as a research note, and tell us if it helped."]] },
];

// Where the card goes: below the lit part, else above, else beside it (a tall sidebar), else in the middle.
const CARD_W = 352, CARD_H = 240;
function place(box) {
  const left = Math.min(Math.max(12, box.left), window.innerWidth - CARD_W);
  if (box.top + box.height + CARD_H < window.innerHeight) return { top: box.top + box.height + 12, left };
  if (box.top - CARD_H > 0) return { top: box.top - 12, left, transform: "translateY(-100%)" };
  const top = Math.min(Math.max(12, box.top + 12), window.innerHeight - CARD_H);
  if (box.left + box.width + CARD_W + 12 < window.innerWidth) return { top, left: box.left + box.width + 12 };
  if (box.left - CARD_W - 12 > 0) return { top, left: box.left - CARD_W - 12 };
  return { top: "50%", left: "50%", transform: "translate(-50%, -50%)" };
}

function seen() {
  try { return localStorage.getItem(KEY) === "1"; } catch { return true; }   // private mode: never insist
}

function visible(selector) {
  const el = selector && document.querySelector(selector);
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return r.width > 0 && r.height > 0 && r.right > 0 && r.left < window.innerWidth ? el : null;
}

export default function Tour() {
  const [step, setStep] = useState(null);                 // null: no tour
  const [box, setBox] = useState(null);                   // where the lit part is

  useEffect(() => {                                       // first visit, or ?tour=1 from Settings
    const asked = new URLSearchParams(window.location.search).get("tour") === "1";
    if (asked) window.history.replaceState(null, "", window.location.pathname);
    if (asked || !seen()) {
      const t = setTimeout(() => setStep(0), 900);        // after the loading screen and the page's own entrance
      return () => clearTimeout(t);
    }
  }, []);

  const close = useCallback(() => {
    setStep(null);
    try { localStorage.setItem(KEY, "1"); } catch { /* private mode */ }
  }, []);

  const go = useCallback((from, dir) => {                 // the next step that is on the screen (or the last card)
    let i = from;
    do { i += dir; } while (i >= 0 && i < STEPS.length && STEPS[i].at && !visible(STEPS[i].at));
    if (i < 0) return;
    if (i >= STEPS.length) close(); else setStep(i);
  }, [close]);

  useEffect(() => {                                       // measure the lit part; again when the window changes
    if (step === null) return;
    const s = STEPS[step];
    if (s.at && !visible(s.at)) { go(step, 1); return; }
    const measure = () => {
      const el = s.at && visible(s.at);
      if (!el) { setBox(null); return; }
      el.scrollIntoView({ block: "nearest" });
      const r = el.getBoundingClientRect();
      setBox({ top: r.top - 8, left: r.left - 8, width: r.width + 16, height: r.height + 16 });
    };
    measure();
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    const keys = (e) => {
      if (e.key === "Escape") close();
      if (e.key === "ArrowRight") go(step, 1);
      if (e.key === "ArrowLeft") go(step, -1);
    };
    window.addEventListener("keydown", keys);
    return () => { window.removeEventListener("resize", measure); window.removeEventListener("scroll", measure, true);
      window.removeEventListener("keydown", keys); };
  }, [step, go, close]);

  if (step === null) return null;
  const s = STEPS[step], last = step === STEPS.length - 1;
  const cardStyle = !box ? {} : place(box);
  return (
    <div className="tour" role="dialog" aria-modal="true" aria-label="Guided tour">
      {box ? <div className="tour-hole" style={box} /> : <div className="tour-veil" />}
      <div className={box ? "tour-card" : "tour-card tour-center"} style={cardStyle}>
        <span className="tour-n">{step + 1} / {STEPS.length}</span>
        <h3>{s.title}</h3>
        {s.text && <p>{s.text}</p>}
        {s.list && <ul>{s.list.map(([k, v]) => <li key={k}><b>{k}</b> {v}</li>)}</ul>}
        <div className="tour-go">
          <button className="tour-skip" onClick={close}>{last ? "Close" : "Skip the tour"}</button>
          {step > 0 && <button className="tour-back" onClick={() => go(step, -1)}>Back</button>}
          <button className="tour-next" onClick={() => go(step, 1)} autoFocus>{last ? "Start asking" : "Next"}</button>
        </div>
      </div>
    </div>
  );
}
