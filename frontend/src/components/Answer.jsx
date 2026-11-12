// One answer of the chat. The results are told apart by TEXT and ICON as well as colour (SR32).
// Only sentences that passed the verifier arrive here; a NOT_SUPPORTED or ERROR answer has none (SR28):
// removed sentences are never sent by the server, so they can never be shown as the answer.
// Props from pages/Chat.jsx: a (the /api/ask answer), onOpen(chunkId, quote) (opens the passage drawer).
// WELCOME (a greeting) shows only our fixed welcome text: there is no passage, citation or score to show.
import { useState } from "react";
import "./answer.css";

const STATUS = {
  ANSWERED: ["✓", "Verified answer", "Every statement below was checked against the passage it cites."],
  LOW_CONFIDENCE: ["⚠", "Low confidence", "The support for this answer is partial. Check the passages before relying on it."],
  NOT_SUPPORTED: ["⊘", "Not supported by the retrieved opinions", "The opinions we searched do not answer this question, so we will not guess."],
  ERROR: ["✕", "The answer service is unavailable right now", "Please try again in a minute."],
  WELCOME: ["✦", "Welcome to Verdicta", ""],     // a greeting: our fixed text (app/pipeline.py), no search, no model
};

// The support score of this answer (0 to 1) as a small ring; the number is written inside it.
function SupportRing({ value }) {
  const r = 15, C = 2 * Math.PI * r;
  return (
    <svg className="an-ring" width="40" height="40" viewBox="0 0 40 40" aria-hidden="true">
      <circle cx="20" cy="20" r={r} fill="none" stroke="rgba(255,255,255,.1)" strokeWidth="4" />
      <circle cx="20" cy="20" r={r} fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round"
              transform="rotate(-90 20 20)" style={{ strokeDasharray: `${Math.max(0, Math.min(1, value)) * C} ${C}` }} />
    </svg>
  );
}

export default function Answer({ a, onOpen }) {
  const [icon, title, text] = STATUS[a.status] || STATUS.ERROR;
  if (a.status === "WELCOME") {
    return (
      <article className={`an st-${a.status}`}>
        <div className="an-status">
          <span className="an-icon" aria-hidden="true">{icon}</span>
          <div><b>{title}.</b> <span>{a.reason}</span></div>
        </div>
      </article>
    );
  }
  const [showPassages, setShowPassages] = useState(a.status === "NOT_SUPPORTED");
  const best = Math.max(0.0001, ...a.passages.map((p) => p.score));
  return (
    <article className={`an st-${a.status}`}>
      <div className="an-status">
        <span className="an-icon" aria-hidden="true">{icon}</span>
        <div>
          <b>{title}.</b> <span>{text}</span>
          {a.status === "LOW_CONFIDENCE" && a.removed_count > 0 &&
            <span> {a.removed_count} statement(s) were removed because they could not be verified.</span>}
          {a.status === "NOT_SUPPORTED" && <span className="an-reason"> ({a.reason})</span>}
        </div>
      </div>

      {a.sentences.length > 0 && (
        <div className="an-text">
          {a.sentences.map((s, i) => (
            <p key={i}>{s.text}{" "}
              {s.citations.map((c, j) => (             // inline citations, each one clickable (brief section 5)
                <button key={j} className="an-cite" onClick={() => onOpen(c.chunk_id, c.quote)}
                        title={`Open passage ${c.pid}: the quote is highlighted`}>
                  <i aria-hidden="true">✓</i>{c.label}<span className="an-cite-n">{c.pid}</span>
                </button>
              ))}
            </p>
          ))}
        </div>
      )}

      <div className="an-meta">
        <span className="an-support" title="How well the kept sentences are supported (0 to 1)">
          <SupportRing value={a.support_score} />Support <b>{a.support_score.toFixed(2)}</b></span>
        <span title="Similarity of the best passage found">Best passage <b>{a.top_score.toFixed(2)}</b></span>
        <span>{(a.ms_total / 1000).toFixed(1)} s</span>
        {a.passages.length > 0 &&
          <button className="an-toggle" onClick={() => setShowPassages(!showPassages)} aria-expanded={showPassages}>
            {showPassages ? "Hide" : "Show"} the {a.passages.length} retrieved passages
          </button>}
      </div>

      {showPassages && a.passages.length > 0 && (       // retrieved passages, shown with the answer (FR5)
        <div className="an-passages">
          {a.passages.map((p) => (
            <button key={p.pid} className="an-passage" onClick={() => onOpen(p.chunk_id, "")}>
              <span className="an-passage-top"><b>{p.pid}</b> {p.case_name} ({p.year})</span>
              <span className="an-passage-label">{p.opinion_label}{p.section ? ` · ${p.section}` : ""}
                {p.is_syllabus && " · Syllabus (not part of the opinion)"}</span>
              <span className="an-passage-text">{p.text}</span>
              <span className="an-score" title={`similarity ${p.score}`}><i style={{ width: `${(p.score / best) * 100}%` }} /></span>
            </button>
          ))}
        </div>
      )}
    </article>
  );
}
