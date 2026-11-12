// Shown while /api/ask runs (2 to 15 s). It names the real steps of the pipeline, in order (app/pipeline.py):
// search, keep 8 passages, the model drafts, the six checks of the verifier, the support score.
// The page cannot see which step the server is on, so the steps advance on a timer and the last one waits
// for the answer. The six dots are the six checks, in their fixed colours.
// Props from pages/Chat.jsx: question (the question being answered).
import { useEffect, useState } from "react";
import "./answer.css";

const CHECK_COLORS = ["#e879f9", "#fb7185", "#a78bfa", "#38bdf8", "#34d399", "#fb923c"];
const STEPS = [
  "Searching the passages by meaning and by keywords",
  "Keeping the 8 best passages",
  "Drafting an answer from those passages only",
  "Six checks on every sentence",
  "Scoring the support and choosing the status",
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
      <div className="an-working" role="status" aria-live="polite">
        <ol>
          {STEPS.map((s, i) => (
            <li key={s} className={i < step ? "done" : i === step ? "now" : ""}>
              <span className="an-step" aria-hidden="true">{i < step ? "✓" : i + 1}</span>{s}
              {i === 3 && (
                <span className="an-six" aria-hidden="true">
                  {CHECK_COLORS.map((c, k) => <i key={c} style={{ "--c": c, animationDelay: `${k * 0.18}s` }} />)}
                </span>
              )}
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
