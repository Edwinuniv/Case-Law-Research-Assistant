// Shown while /api/ask runs (2 to 15 s). It names the real steps of the pipeline in order; the page cannot
// see which step the server is on, so the steps advance on a timer and the last one waits for the answer.
import { useEffect, useState } from "react";

const STEPS = [
  "Searching the passages by meaning and keywords",
  "Keeping the 8 best passages",
  "Drafting an answer from those passages only",
  "Checking every citation and quote",
];

export default function Working({ question }) {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 1500);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="rs-turn">
      {question && <p className="rs-question">{question}</p>}
      <div className="rs-working" role="status" aria-live="polite">
        <div className="rs-spinner" aria-hidden="true" />
        <ol>
          {STEPS.map((s, i) => (
            <li key={s} className={i < step ? "done" : i === step ? "now" : ""}>{s}</li>
          ))}
        </ol>
      </div>
    </div>
  );
}
