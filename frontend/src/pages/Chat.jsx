// The research page "Ask the Court", open to visitors (SR33). Each question is sent ALONE to /api/ask: the
// pipeline does not use earlier questions (FR1), and the page says so.
// "My questions": for a visitor without an account it lives only in this page (React memory) and reloading
// empties it; with an account (SPEC 11, 2026-11-12) it comes from GET /api/history, the account's own questions,
// and an earlier answer is read back from /api/history/{id} as it was shown (no new model call).
// Redesigned 2026-11-12 (Yasser): dark like the landing page; the calls to the server are the same as before.
// A visitor without an account has ONE question per browser session (SPEC 11, 2026-11-14); the server counts it and
// refuses the next one. After it, the page shows "Log in or sign up" instead of the question box. The example
// questions (saved answers) stay open: clicking one sends it at once.
// A logged-in account keeps CHATS (SPEC 11, 2026-11-14): "My chats" comes from GET /api/chats; a question is sent with
// the open chat's id (none: the server starts a new chat). Whether the model reads the chat's earlier answers is the
// server's setting follow_ups (off until Edwin's measurement); the page only says which.
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, me } from "../api.js";
import Logo from "../components/Logo.jsx";   // the Verdicta logo for the theme (Edwin, 2026-11-19; was the seal)
import Answer from "../components/Answer.jsx";
import PassagePanel from "../components/PassagePanel.jsx";
import PlansDialog from "../components/PlansDialog.jsx";   // the plans panel (Edwin, 2026-11-16)
import Working from "../components/Working.jsx";
import { CopyButton, Navigator, PenIcon, Versions } from "../components/ChatTools.jsx";   // Edwin, SPEC 11, 2026-11-21
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

// Edit and versions (Edwin, SPEC 11, 2026-11-21): every question remembers its parent, the answer it followed; an edit
// is a new question with the same parent, so the versions of one place are siblings. The page shows one path: at each
// place the version picked ("< 1 / 2 >"), by default the newest, then the questions asked after it.
function shownPath(nodes, pick) {
  const path = [];
  let parent = null;
  for (;;) {
    const siblings = nodes.filter((n) => n.parent === parent);
    if (siblings.length === 0) return path;
    const node = siblings.find((n) => n.id === pick[parent ?? "root"]) || siblings[siblings.length - 1];
    path.push({ node, index: siblings.indexOf(node), siblings });
    parent = node.id;
  }
}

export default function Chat({ info }) {
  const [nodes, setNodes] = useState([]);          // every question asked on this page or in the open chat, with its answer
  const [pick, setPick] = useState({});            // parent id ("root" for none) -> the version shown
  const [editing, setEditing] = useState(null);    // {id, text}: a question being edited
  const turns = shownPath(nodes, pick);            // what is on screen
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState("");     // the question being answered right now
  const [error, setError] = useState("");
  const [history, setHistory] = useState([]);      // newest first: this page's questions, or the account's
  const [open, setOpen] = useState(null);          // the passage shown in the side drawer
  const [saved, setSaved] = useState(new Set());   // an account's saved answers (Edwin, SPEC 11, 2026-11-20)
  const [panel, setPanel] = useState(false);       // phone: "My questions" opened
  const bottom = useRef(null);
  const box = useRef(null);

  const account = info.user;                       // logged in: the history is kept on the server
  const [chatId, setChatId] = useState(null);      // the account's open chat (null: the next question starts one)
  const [left, setLeft] = useState(info.free_questions_left);   // a visitor's free questions; null with an account
  useEffect(() => { setLeft(info.free_questions_left); }, [account?.email]);
  const locked = !account && left === 0;
  const [plan, setPlan] = useState(info.plan);
  const [plansOpen, setPlansOpen] = useState(false);       // the plans panel over the chat    // a 'user' account: {plan, daily_limit, left_today} (SPEC 11)
  useEffect(() => {                               // asked again at each login: info.plan was loaded before it (Edwin)
    if (account) me().then((m) => setPlan(m.plan)).catch(() => setPlan(info.plan));
    else setPlan(null);
  }, [account?.email]);           // the free question is used: no question box
  const loadChats = () => api("/chats").then((list) => setHistory(list)).catch(() => {});
  useEffect(() => {
    setChatId(null);
    if (!account) { setHistory([]); return; }
    loadChats();
  }, [account?.email]);

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [nodes.length, busy]);
  useEffect(() => {                                // which answers this account saved (Edwin, SPEC 11, 2026-11-20)
    if (account) api("/bookmarks").then((b) => setSaved(new Set(b.map((x) => x.query_id))), () => {});
  }, [account?.email]);
  async function toggleSave(id) {
    const r = await api("/bookmarks", { query_id: id, saved: !saved.has(id) });
    const next = new Set(saved);
    if (r.saved) next.add(id); else next.delete(id);
    setSaved(next);
  }

  useEffect(() => {                                // the box grows with the question, up to 6 lines
    const t = box.current;
    if (!t) return;
    t.style.height = "auto";
    t.style.height = `${Math.min(t.scrollHeight, 6 * 26 + 16)}px`;
  }, [question]);

  async function ask(e, text, editOf) {          // editOf: the question edited (its new version gets the same parent)
    e?.preventDefault();
    const q = text ?? question;
    if (!q.trim() || busy) return false;
    const parent = editOf ? editOf.parent : (turns.length ? turns[turns.length - 1].node.id : null);
    setBusy(true); setError(""); setPending(q); if (!editOf) setQuestion("");
    try {
      const body = { question: q };
      if (account) {                               // an account: the server keeps the tree with the chat
        if (chatId) body.chat_id = chatId;
        body.parent_id = parent;
      }
      const a = await api("/ask", body);
      const id = a.id ?? `page-${Date.now()}`;
      setNodes((n) => [...n, { id, question: a.question, answer: a, parent }]);
      setPick((p) => ({ ...p, [parent ?? "root"]: id }));
      if (account) { setChatId(a.chat_id); loadChats(); }          // the chat moves to the top of "My chats"
      else setHistory((h) => [{ id: a.id, question: a.question, status: a.status, answer: a }, ...h]);
      if (!account && !a.demo && !["WELCOME", "ERROR"].includes(a.status)) setLeft(0);   // as the server counts
      if (plan) api("/me").then((m) => setPlan(m.plan)).catch(() => {});               // the questions left today
    } catch (err) {
      if (!account && err.message.startsWith("You have used your free question")) setLeft(0);
      else setError(err.message);                  // e.g. the SR3 length message, or the 429 wait
      if (text === undefined) setQuestion(q);      // give the question back so it can be sent again
      return false;
    } finally {
      setBusy(false);
    }
    return true;
  }

  async function sendEdit(node) {                   // a new version beside the old one; nothing is deleted
    const text = editing.text.trim();
    if (!text || text === node.question) { setEditing(null); return; }
    if (await ask(null, text, node)) setEditing(null);
  }

  function onKey(e) {                               // Enter sends, Shift+Enter makes a new line
    if (e.key === "Enter" && !e.shiftKey) ask(e);
  }

  async function showEarlier(h) {                  // a visitor: an earlier answer from this page's memory
    setPanel(false);
    if (account) return openChat(h);
    const parent = turns.length ? turns[turns.length - 1].node.id : null;
    const id = `earlier-${h.id}-${Date.now()}`;
    setNodes((n) => [...n, { id, question: h.question, answer: h.answer, parent, earlier: true }]);
    setPick((p) => ({ ...p, [parent ?? "root"]: id }));
  }

  async function openChat(c) {                     // an account: an earlier chat, shown as it was, and continued
    setError("");
    try {
      const chat = await api(`/chats/${c.id}`);
      const rows = chat.turns.filter((t) => t.shown);
      const ids = new Set(rows.map((t) => t.id));
      let before = null;                            // a chat saved before 2026-11-21 has no parents: one line
      setNodes(rows.map((t) => {
        const parent = t.linked ? (ids.has(t.parent) ? t.parent : null) : before;
        before = t.id;
        return { id: t.id, question: t.question, answer: t.shown, parent };
      }));
      setPick({}); setEditing(null);
      setChatId(chat.id);
    } catch (err) { setError(err.message); }
  }

  function newQuestion() {                          // a clean page (an account: a new chat); the list stays
    setNodes([]); setPick({}); setEditing(null); setError(""); setQuestion(""); setPanel(false); setChatId(null);
    setTimeout(() => box.current?.focus(), 0);
  }

  const started = nodes.length > 0 || busy;

  return (
    <div className={`rs ${started ? "started" : ""}`}>
      <div className="rs-bg" aria-hidden="true" />

      <aside className={`rs-side ${panel ? "open" : ""}`} aria-label="My questions">
        <button className="rs-new" onClick={newQuestion} disabled={busy}><span aria-hidden="true">+</span> {account ? "New chat" : "New question"}</button>
        {account?.role === "admin" && (   /* back to the admin pages (Edwin, 2026-11-19); the server checks the role */
          <Link to="/admin" className="rs-to-admin"><span aria-hidden="true">←</span> Admin pages</Link>
        )}
        {account?.role === "user" && <Link to="/account" className="rs-to-admin">My account</Link>}
        {account && <Link to="/saved" className="rs-to-admin">★ Saved answers</Link>}
        <div className="rs-side-head">
          <b>{account ? "My chats" : "My questions"}</b>
          <span className="rs-count">{history.length}</span>
        </div>
        <p className="rs-side-note">
          {account ? <>Saved to your account.{plan && <><br /><span className="rs-plan">{plan.plan === "paid" ? "Paid" : "Free"} plan
            · {plan.left_today} of {plan.daily_limit} questions left today · <button className="pl-link" onClick={() => setPlansOpen(true)}>Plans</button></span></>}
            {info.unlimited && <><br /><span className="rs-plan">Administrator · no limit</span></>}</> : <>Only in this page: they are gone when you reload it. <Link to="/signup">Sign up</Link> to keep them.</>}
        </p>
        <div className="rs-list">
          {history.length === 0 && <p className="rs-empty">{account ? "Your chats" : "Your questions"} will appear here.</p>}
          {history.map((h) => account ? (
            <button key={h.id} onClick={() => showEarlier(h)} title={`${h.questions} question(s)`}
                    className={h.id === chatId ? "on" : ""}>
              <i className="rs-dot" /><span>{h.title}</span>
            </button>
          ) : (
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
          {started && <button className="rs-bar-new" onClick={newQuestion} disabled={busy}>{account ? "+ New chat" : "+ New question"}</button>}
        </div>

        {!started && (
          <div className="rs-hero">
            <Logo className="rs-seal" />
            <span className="rs-kicker">Verified case-law research</span>
            <h1>Ask the <em>Court.</em></h1>
            <p className="rs-sub">Answers come only from {info.coverage}. Every citation and every quote is checked against
              the opinion itself before you see it.</p>
          </div>
        )}

        <div className="rs-thread">
          {turns.map(({ node: t, index, siblings }) => (
            <div key={t.id} id={`q-${t.id}`} className="rs-turn">
              {editing?.id === t.id ? (
                <div className="ct-edit">
                  <textarea value={editing.text} maxLength={MAX} autoFocus aria-label="Edit your question"
                            onChange={(e) => setEditing({ ...editing, text: e.target.value })}
                            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendEdit(t); }
                                                if (e.key === "Escape") setEditing(null); }} />
                  <div className="ct-edit-bar">
                    <button type="button" onClick={() => setEditing(null)}>Cancel</button>
                    <button type="button" className="main" onClick={() => sendEdit(t)}
                            disabled={busy || !editing.text.trim()}>Send</button>
                  </div>
                  <p className="ct-edit-note">Sent as a new question; the first version stays, switch with ‹ ›.</p>
                </div>
              ) : (
                <>
                  <p className="rs-question">{t.question}{t.earlier && <span> · earlier answer</span>}</p>
                  <div className="ct-row">
                    <CopyButton text={t.question} label="Copy your question" />
                    {!locked && !t.earlier && (
                      <button type="button" className="ct-icon" onClick={() => setEditing({ id: t.id, text: t.question })}
                              disabled={busy} aria-label="Edit your question" title="Edit"><PenIcon /></button>
                    )}
                    <Versions index={index} count={siblings.length}
                              onPick={(k) => setPick((p) => ({ ...p, [t.parent ?? "root"]: siblings[k].id }))} />
                  </div>
                </>
              )}
              <Answer a={t.answer} onOpen={(chunkId, quote) => setOpen({ chunkId, quote })}
                      save={account && t.answer.id ? { saved: saved.has(t.answer.id), toggle: () => toggleSave(t.answer.id) } : undefined} />
            </div>
          ))}
          {busy && <Working question={pending} />}
          <div ref={bottom} />
        </div>
        {started && <Navigator ids={turns.map((x) => x.node.id)} titles={turns.map((x) => x.node.question)} />}

        {account && info.email_verified === false && (     /* SPEC 11, 2026-11-20: one question until verified */
          <p className="rs-verify" role="status"><b>Verify your email</b> to keep asking: type the code we sent to{" "}
            {account.email}. <Link to="/verify">Enter the code</Link></p>
        )}
        {locked ? (
          <div className="rs-ask">
            <div className="rs-locked" role="status">
              <b>You have used your free question.</b>
              <p>Log in or create a free account to keep asking and to keep your questions.
                The example questions stay open.</p>
              <div className="rs-locked-go">
                <Link to="/login" className="rs-locked-btn">Log in</Link>
                <Link to="/signup" className="rs-locked-btn main">Sign up</Link>
              </div>
            </div>
          </div>
        ) : (
        <form className="rs-ask" onSubmit={ask}>
          <div className="rs-box" onClick={() => box.current?.focus()}>
            <textarea ref={box} rows={1} maxLength={MAX} required value={question} aria-label="Your question"
                      placeholder={started ? "Ask another question…" : "Ask a question about a Supreme Court decision…"}
                      onChange={(e) => setQuestion(e.target.value)} onKeyDown={onKey} disabled={busy} />
            <div className="rs-box-bar">
              <span className="rs-chip"><i style={{ background: "#34d399" }} />Citations verified</span>
              <span className="rs-chip hide-sm">{account && info.follow_ups ? "Follow-ups read this chat" : "Each question answered on its own"}</span>
              <span className={`rs-counter ${question.length > MAX * 0.9 ? "near" : ""}`}>{question.length}/{MAX}</span>
              <button className="rs-send" disabled={busy || !question.trim()} aria-label="Ask">
                {busy ? <span className="rs-spin" /> : <Arrow />}
              </button>
            </div>
          </div>
          {error && <p className="rs-error" role="alert">{error}</p>}
          {!started && <p className="rs-hint">Enter to send · Shift+Enter for a new line · earlier questions are not used
            {!account && " · without an account: one question"}</p>}
        </form>
        )}

        {!started && (
          <>
            <div className="rs-examples">
              {info.examples.map((ex, k) => (                     // SR30
                <button type="button" key={ex} className="rs-example" onClick={() => { if (locked) ask(null, ex); else { setQuestion(ex); box.current?.focus(); } }}
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
      <PlansDialog open={plansOpen} onClose={() => setPlansOpen(false)} onChange={(m) => setPlan(m.plan)} />
    </div>
  );
}
