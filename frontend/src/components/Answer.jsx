// One answer of the chat. The three results are told apart by TEXT and ICON, not only colour (SR32).
// Only sentences that passed the verifier arrive here; a NOT_SUPPORTED answer has none (SR28).
import { useState } from "react";

const STATUS = {
  ANSWERED: ["✓", "Verified answer", "Every statement below was checked against the passage it cites."],
  LOW_CONFIDENCE: ["⚠", "Low confidence", "The support for this answer is partial. Check the passages before relying on it."],
  NOT_SUPPORTED: ["⊘", "Not supported by the retrieved opinions", "The opinions we searched do not answer this question, so we will not guess."],
  ERROR: ["✕", "The answer service is unavailable right now", "Please try again in a minute."],
};

export default function Answer({ a, onOpen }) {
  const [icon, title, text] = STATUS[a.status] || STATUS.ERROR;
  const [showPassages, setShowPassages] = useState(a.status === "NOT_SUPPORTED");
  const best = Math.max(0.0001, ...a.passages.map((p) => p.score));
  return (
    <article className={`rs-answer st-${a.status}`}>
      <div className="rs-status">
        <span className="rs-icon" aria-hidden="true">{icon}</span>
        <div>
          <b>{title}.</b> <span>{text}</span>
          {a.status === "LOW_CONFIDENCE" && a.removed_count > 0 &&
            <span> {a.removed_count} statement(s) were removed because they could not be verified.</span>}
          {a.status === "NOT_SUPPORTED" && <span className="muted"> ({a.reason})</span>}
        </div>
      </div>

      {a.sentences.length > 0 && (
        <div className="rs-text">
          {a.sentences.map((s, i) => (
            <p key={i}>{s.text}{" "}
              {s.citations.map((c, j) => (             // inline citations, each one clickable (brief section 5)
                <button key={j} className="rs-cite" onClick={() => onOpen(c.chunk_id, c.quote)} title="Open the passage">
                  <span className="rs-cite-n">{c.pid}</span>{c.label}
                </button>
              ))}
            </p>
          ))}
        </div>
      )}

      <div className="rs-meta">
        <span title="How well the kept sentences are supported (0 to 1)">Support <b>{a.support_score.toFixed(2)}</b></span>
        <span title="Similarity of the best passage found">Best passage <b>{a.top_score.toFixed(2)}</b></span>
        <span>{(a.ms_total / 1000).toFixed(1)} s</span>
        {a.passages.length > 0 &&
          <button className="rs-toggle" onClick={() => setShowPassages(!showPassages)} aria-expanded={showPassages}>
            {showPassages ? "Hide" : "Show"} the {a.passages.length} retrieved passages
          </button>}
      </div>

      {showPassages && a.passages.length > 0 && (       // retrieved passages, shown with the answer (FR5)
        <div className="rs-passages">
          {a.passages.map((p) => (
            <button key={p.pid} className="rs-passage" onClick={() => onOpen(p.chunk_id, "")}>
              <span className="rs-passage-top">
                <b>{p.pid}</b> {p.case_name} ({p.year})
              </span>
              <span className="rs-passage-label">{p.opinion_label}{p.section ? ` · ${p.section}` : ""}
                {p.is_syllabus && " · Syllabus (not part of the opinion)"}</span>
              <span className="rs-passage-text">{p.text}</span>
              <span className="rs-score" title={`score ${p.score}`}><i style={{ width: `${(p.score / best) * 100}%` }} /></span>
            </button>
          ))}
        </div>
      )}
    </article>
  );
}
