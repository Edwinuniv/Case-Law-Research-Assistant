// The research page "Ask the Court", open to visitors (SR33). Each question is sent ALONE to /api/ask: the
// pipeline does not use earlier questions (FR1), and the page says so.
// "My questions": for a visitor without an account it lives only in this page (React memory) and reloading
// empties it; with an account (SPEC 11, 2026-11-12) it comes from GET /api/history, the account's own questions,
// and an earlier answer is read back from /api/history/{id} as it was shown (no new model call).
// Redesigned 2026-11-12 (Yasser): dark like the landing page; the calls to the server are the same as before.
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import seal from "../assets/logo-seal.webp";
import Answer from "../components/Answer.jsx";
import PassagePanel from "../components/PassagePanel.jsx";
import Working from "../components/Working.jsx";
import "./research.css";

const MAX = 1000;                                    // the longest question the server accepts (SR3)
// how every answer is made, in three steps (the same numbers as the landing page)
const STEPS = [
  ["Search", "72,502 passages of 2,415 decisions, by meaning and by keywords."],
  ["Draft", "The model writes only from the best 8 passages it receives."],
  ["Verify", "Six checks on every sentence; what fails is removed."],
];
const COLORS = ["#e879f9", "#fb7185", "#a78bfa", "#38bdf8", "#34d399", "#fb923c"];   // the six checks

const Arrow = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14" /><path d="M13 6l6 6-6 6" /></svg>
);

export default function Chat({ info }) {
  const [turns, setTurns] = useState([]);          // [{question, answer}] shown on the page
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState("");     // the question being answered right now
  const [error, setError] = useState("");
  const [history, setHistory] = useState([]);      // newest first: this page's questions, or the account's
  const [open, setOpen] = useState(null);          // the passage shown in the side drawer
  const [panel, setPanel] = useState(false);       // phone: "My questions" opened
  const bottom = useRef(null);
  const box = useRef(null);

  const account = info.user;                       // logged in: the history is kept on the server
  useEffect(() => {
    if (!account) { setHistory([]); return; }
    api("/history").then((list) => setHistory(list)).catch(() => {});
  }, [account?.email]);

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [turns, busy]);

  useEffect(() => {                                // the box grows with the question, up to 6 lines
    const t = box.current;
    if (!t) return;
    t.style.height = "auto";
    t.style.height = `${Math.min(t.scrollHeight, 6 * 26 + 16)}px`;
  }, [question]);

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
    setPanel(false);
    let answer = h.answer;
    if (!answer) {
      try { answer = (await api(`/history/${h.id}`)).shown; } catch (err) { setError(err.message); return; }
      if (!answer) { setError("This earlier answer was not saved."); return; }
    }
    setTurns((t) => [...t, { question: h.question, answer, earlier: true }]);
  }

  function newQuestion() {                          // a clean page; the history stays
    setTurns([]); setError(""); setQuestion(""); setPanel(false);
    setTimeout(() => box.current?.focus(), 0);
  }

  const started = turns.length > 0 || busy;

  return (
    <div className={`rs ${started ? "started" : ""}`}>
      <div className="rs-bg" aria-hidden="true" />

      <aside className={`rs-side ${panel ? "open" : ""}`} aria-label="My questions">
        <button className="rs-new" onClick={newQuestion}><span aria-hidden="true">+</span> New question</button>
        <div className="rs-side-head">
          <b>My questions</b>
          <span className="rs-count">{history.length}</span>
        </div>
        <p className="rs-side-note">
          {account ? "Saved to your account." : <>Only in this page: they are gone when you reload it. <Link to="/signup">Sign up</Link> to keep them.</>}
        </p>
        <div className="rs-list">
          {history.length === 0 && <p className="rs-empty">Your questions will appear here.</p>}
          {history.map((h) => (
            <button key={h.id} onClick={() => showEarlier(h)} title={h.status}>
              <i className={`rs-dot st-${h.status}`} /><span>{h.question}</span>
            </button>
          ))}
        </div>
      </aside>
      {panel && <div className="rs-scrim" onClick={() => setPanel(false)} />}

      <section className="rs-main">
        <div className="rs-bar">
          <button className="rs-panel-btn" onClick={() => setPanel(true)} aria-label="Show my questions">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h10" /></svg>
          </button>
          <span className="rs-bar-title">Ask the Court</span>
          <span className="rs-bar-meta">U.S. Supreme Court · 2000–2024</span>
          {started && <button className="rs-bar-new" onClick={newQuestion}>+ New question</button>}
        </div>

        {!started && (
          <div className="rs-hero">
            <img src={seal} alt="" className="rs-seal" />
            <span className="rs-kicker">Verified case-law research</span>
            <h1>Ask the <em>Court.</em></h1>
            <p className="rs-sub">Answers come only from {info.coverage}. Every citation and every quote is checked against
              the opinion itself before you see it.</p>
          </div>
        )}

        <div className="rs-thread">
          {turns.map((t, i) => (
            <div key={i} className="rs-turn">
              <p className="rs-question">{t.question}{t.earlier && <span> · earlier answer</span>}</p>
              <Answer a={t.answer} onOpen={(chunkId, quote) => setOpen({ chunkId, quote })} />
            </div>
          ))}
          {busy && <Working question={pending} />}
          <div ref={bottom} />
        </div>

        <form className="rs-ask" onSubmit={ask}>
          <div className="rs-box" onClick={() => box.current?.focus()}>
            <textarea ref={box} rows={1} maxLength={MAX} required value={question} aria-label="Your question"
                      placeholder={started ? "Ask another question…" : "Ask a question about a Supreme Court decision…"}
                      onChange={(e) => setQuestion(e.target.value)} onKeyDown={onKey} disabled={busy} />
            <div className="rs-box-bar">
              <span className="rs-chip"><i style={{ background: "#34d399" }} />Citations verified</span>
              <span className="rs-chip hide-sm">Each question answered on its own</span>
              <span className={`rs-counter ${question.length > MAX * 0.9 ? "near" : ""}`}>{question.length}/{MAX}</span>
              <button className="rs-send" disabled={busy || !question.trim()} aria-label="Ask">
                {busy ? <span className="rs-spin" /> : <Arrow />}
              </button>
            </div>
          </div>
          {error && <p className="rs-error" role="alert">{error}</p>}
          {!started && <p className="rs-hint">Enter to send · Shift+Enter for a new line · earlier questions are not used</p>}
        </form>

        {!started && (
          <>
            <div className="rs-examples">
              {info.examples.map((ex, k) => (                     // SR30
                <button type="button" key={ex} className="rs-example" onClick={() => { setQuestion(ex); box.current?.focus(); }}
                        style={{ animationDelay: `${0.25 + k * 0.08}s` }}>
                  <span className="rs-example-n">Example {k + 1}</span>
                  <span className="rs-example-q">{ex}</span>
                  <span className="rs-example-go"><Arrow /></span>
                </button>
              ))}
            </div>

            <div className="rs-how">
              {STEPS.map(([t, d], k) => (
                <div key={t} className="rs-how-step">
                  <span className="rs-how-n">{k + 1}</span>
                  <div><b>{t}</b><p>{d}</p></div>
                  {k === 2 && <span className="rs-six" aria-hidden="true">{COLORS.map((c) => <i key={c} style={{ background: c }} />)}</span>}
                </div>
              ))}
            </div>
          </>
        )}

        <div className="rs-foot">
          <span>This is a research aid, not legal advice. · Data: CourtListener (Free Law Project), public domain.</span>
          <nav aria-label="Site information">
            <Link to="/privacy">Privacy</Link><Link to="/terms">Terms of use</Link>
            <Link to="/sources">Sources &amp; licences</Link><Link to="/contact">Contact</Link>
          </nav>
        </div>
      </section>

      <PassagePanel open={open} onClose={() => setOpen(null)} />
    </div>
  );
}
