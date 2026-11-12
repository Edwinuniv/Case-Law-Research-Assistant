// The research page, open to visitors (SR33). Each question is sent ALONE to /api/ask: the pipeline does
// not use earlier questions (FR1), and the page says so.
// "My questions": for a visitor without an account it lives only in this page (React memory) and reloading
// empties it; with an account (SPEC 11, 2026-11-12) it comes from GET /api/history, the account's own questions,
// and an earlier answer is read back from /api/history/{id} as it was shown (no new model call).
// The look changed (landing-page branch); the calls to the server are exactly the same as before.
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import Answer from "../components/Answer.jsx";
import PassagePanel from "../components/PassagePanel.jsx";
import Working from "../components/Working.jsx";
import "./research.css";

export default function Chat({ info }) {
  const [turns, setTurns] = useState([]);          // [{question, answer}] shown on the page
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState("");     // the question being answered right now
  const [error, setError] = useState("");
  const [history, setHistory] = useState([]);      // the questions asked in this page, newest first
  const [open, setOpen] = useState(null);          // the passage shown in the side drawer
  const bottom = useRef(null);
  const box = useRef(null);

  const account = info.user;                       // logged in: the history is kept on the server
  useEffect(() => {
    if (!account) { setHistory([]); return; }
    api("/history").then((list) => setHistory(list)).catch(() => {});
  }, [account?.email]);

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [turns, busy]);

  async function ask(e) {
    e?.preventDefault();
    if (!question.trim() || busy) return;
    const q = question;
    setBusy(true); setError(""); setPending(q); setQuestion("");
    try {
      const a = await api("/ask", { question: q });
      setTurns((t) => [...t, { question: a.question, answer: a }]);
      setHistory((h) => [{ id: a.id, question: a.question, status: a.status, answer: a }, ...h]);
    } catch (err) {
      setError(err.message);                       // e.g. the SR3 length message, or the 429 wait
      setQuestion(q);                              // give the question back so it can be sent again
    } finally {
      setBusy(false);
    }
  }

  function onKey(e) {                               // Enter sends, Shift+Enter makes a new line
    if (e.key === "Enter" && !e.shiftKey) ask(e);
  }

  async function showEarlier(h) {                  // an earlier answer: from memory, or from the account's history
    let answer = h.answer;
    if (!answer) {
      try { answer = (await api(`/history/${h.id}`)).shown; } catch (err) { setError(err.message); return; }
      if (!answer) { setError("This earlier answer was not saved."); return; }
    }
    setTurns((t) => [...t, { question: h.question, answer, earlier: true }]);
  }

  const started = turns.length > 0 || busy;

  return (
    <div className={`rs ${started ? "started" : ""} ${history.length ? "has-history" : ""}`}>
      <section className="rs-hero">
        <h1>Ask the Court.</h1>
        <p className="rs-sub">Answers come only from {info.coverage}. Every citation is checked before it is shown.</p>
      </section>

      <div className="rs-body">
        <aside className="rs-history">
          <b>My questions</b>
          {account
            ? <p className="muted">Saved to your account.</p>
            : <p className="muted">Only in this page: they are gone when you reload it. <Link to="/signup">Sign up</Link> to keep them.</p>}
          {history.length === 0 && <p className="muted">None yet.</p>}
          {history.map((h) => (
            <button key={h.id} onClick={() => showEarlier(h)} title={h.status}>
              <span className={`rs-dot st-${h.status}`} />{h.question}
            </button>
          ))}
        </aside>

        <section className="rs-thread">
          {turns.map((t, i) => (
            <div key={i} className="rs-turn">
              <p className="rs-question">{t.question}{t.earlier && <span> · earlier answer</span>}</p>
              <Answer a={t.answer} onOpen={(chunkId, quote) => setOpen({ chunkId, quote })} />
            </div>
          ))}
          {busy && <Working question={pending} />}
          <div ref={bottom} />

          <form className="rs-ask" onSubmit={ask}>
            <div className="rs-box" onClick={() => box.current?.focus()}>
              <textarea ref={box} rows={started ? 1 : 2} maxLength={1000} required value={question}
                        placeholder="Ask a question about a Supreme Court decision…"
                        onChange={(e) => setQuestion(e.target.value)} onKeyDown={onKey} disabled={busy} />
              <button disabled={busy || !question.trim()} aria-label="Ask">{busy ? "…" : "Ask"}</button>
            </div>
            {error && <p className="error" role="alert">{error}</p>}
            <p className="rs-note">Each question is answered on its own: earlier questions are not used. Enter to send,
              Shift+Enter for a new line.</p>
            {!started && (
              <div className="rs-examples">
                <span className="muted">Try:</span>
                {info.examples.map((ex) => (                      // SR30
                  <button type="button" key={ex} className="rs-example" onClick={() => setQuestion(ex)}>{ex}</button>
                ))}
              </div>
            )}
          </form>
        </section>
      </div>

      <PassagePanel open={open} onClose={() => setOpen(null)} />
    </div>
  );
}
