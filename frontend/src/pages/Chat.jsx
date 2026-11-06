// The research page as a conversation, open to visitors (SR33). Each question is sent ALONE to /api/ask:
// the pipeline does not use earlier questions (FR1), and the page says so.
// "My questions" lives only in this page (React memory): visitors have no account, so nothing is
// kept on the server for them, and reloading the page empties the list.
import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import Answer from "../components/Answer.jsx";
import PassagePanel from "../components/PassagePanel.jsx";

export default function Chat({ info }) {
  const [turns, setTurns] = useState([]);          // [{question, answer}] shown on the page
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [history, setHistory] = useState([]);      // the questions asked in this page, newest first
  const [open, setOpen] = useState(null);          // the passage shown in the side panel
  const bottom = useRef(null);

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth" }); }, [turns]);

  async function ask(e) {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const a = await api("/ask", { question });
      setTurns((t) => [...t, { question: a.question, answer: a }]);
      setHistory((h) => [{ id: a.id, question: a.question, status: a.status, answer: a }, ...h]);
      setQuestion("");
    } catch (err) {
      setError(err.message);                       // e.g. the SR3 length message
    } finally {
      setBusy(false);
    }
  }

  function showEarlier(h) {                        // an earlier answer, from memory (no new model call)
    setTurns((t) => [...t, { question: h.question, answer: h.answer, earlier: true }]);
  }

  return (
    <div className="layout">
      <aside className="card history">
        <b>My questions</b>
        {history.length === 0 && <p className="muted">None yet.</p>}
        {history.map((h) => (
          <button key={h.id} onClick={() => showEarlier(h)} title={h.status}>{h.question}</button>
        ))}
      </aside>

      <section>
        <div className="card">
          <b>Ask a legal research question</b><br />
          <span className="muted">Answers come only from {info.coverage}. Every citation is checked before it is shown.
            Each question is answered on its own: earlier questions are not used.</span>
        </div>

        {turns.map((t, i) => (
          <div key={i}>
            <p className="question">{t.question}{t.earlier && <span className="muted" style={{ color: "#c9d6e8" }}> (earlier answer)</span>}</p>
            <Answer a={t.answer} onOpen={(chunkId, quote) => setOpen({ chunkId, quote })} />
          </div>
        ))}
        {busy && <p className="muted">Searching the opinions and checking every citation…</p>}
        <div ref={bottom} />

        <form className="card" onSubmit={ask}>
          <textarea rows={3} maxLength={1000} required value={question} placeholder="Type your question"
                    onChange={(e) => setQuestion(e.target.value)} />
          {error && <p className="error" role="alert">{error}</p>}
          <p><button disabled={busy}>{busy ? "Working…" : "Ask"}</button>{" "}
            <span className="muted">Examples:</span>
            {info.examples.map((ex) => (                      // SR30
              <button type="button" key={ex} className="chip" onClick={() => setQuestion(ex)}>{ex}</button>
            ))}
          </p>
        </form>
      </section>

      <PassagePanel open={open} />
    </div>
  );
}
