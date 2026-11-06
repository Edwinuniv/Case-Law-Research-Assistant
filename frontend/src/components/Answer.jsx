// One answer of the chat. The three results are told apart by TEXT and ICON, not only colour (SR32).
// Only sentences that passed the verifier arrive here; a NOT_SUPPORTED answer has none (SR28).

const STATUS = {
  ANSWERED: ["✓", "Verified answer.", "Every statement below was checked against the passage it cites."],
  LOW_CONFIDENCE: ["⚠", "Low confidence.", "The support for this answer is partial. Check the passages before relying on it."],
  NOT_SUPPORTED: ["⊘", "Not supported by the retrieved opinions.", "The opinions we searched do not answer this question, so we will not guess."],
  ERROR: ["✕", "The answer service is unavailable right now.", "Please try again in a minute."],
};

export default function Answer({ a, onOpen }) {
  const [icon, title, text] = STATUS[a.status] || STATUS.ERROR;
  return (
    <div className="card">
      <div className={"status " + a.status}>
        <b>{icon} {title}</b> {text}
        {a.status === "LOW_CONFIDENCE" && a.removed_count > 0 &&
          <> {a.removed_count} statement(s) were removed because they could not be verified.</>}
        {a.status === "NOT_SUPPORTED" && <span className="muted"> ({a.reason})</span>}
      </div>

      {a.sentences.map((s, i) => (
        <p key={i}>{s.text}{" "}
          {s.citations.map((c, j) => (               // inline citations, each one clickable (brief section 5)
            <button key={j} className="chip" onClick={() => onOpen(c.chunk_id, c.quote)}>{c.label}</button>
          ))}
        </p>
      ))}
      <p className="muted">Support score {a.support_score.toFixed(2)} · best passage {a.top_score.toFixed(2)} · {a.ms_total} ms</p>

      {a.passages.length > 0 && (                     // retrieved passages, shown with the answer (FR5)
        <details>
          <summary>Retrieved passages ({a.passages.length})</summary>
          {a.passages.map((p) => (
            <details key={p.pid} style={{ marginLeft: 12 }}>
              <summary>
                <b>[{p.pid}]</b> {p.case_name} ({p.year}) — {p.opinion_label} — {p.section}
                {p.is_syllabus && <i> — Syllabus (not part of the opinion)</i>}
                <span className="muted"> score {p.score}</span>
              </summary>
              <p style={{ whiteSpace: "pre-wrap" }}>{p.text}</p>
              <button className="chip" onClick={() => onOpen(p.chunk_id, "")}>Show in the opinion</button>
            </details>
          ))}
        </details>
      )}
    </div>
  );
}
