// Saved answers (Edwin, SPEC 11, 2026-11-20, from CedarPay's saved beneficiaries): an account's saved answers, newest
// saved first; each opens as it was shown (GET /api/answers/{id}: no model call), with its citations and passages.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import Answer from "../components/Answer.jsx";
import PassagePanel from "../components/PassagePanel.jsx";
import SitePage from "./SitePage.jsx";

const STATUS = { ANSWERED: "Verified answer", LOW_CONFIDENCE: "Low confidence", NOT_SUPPORTED: "Not supported" };

export default function Saved() {
  const [list, setList] = useState(null);
  const [opened, setOpened] = useState({});            // query_id -> the answer, once opened
  const [shown, setShown] = useState(null);            // which one is open
  const [passage, setPassage] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { api("/bookmarks").then(setList, (e) => setError(e.message)); }, []);

  async function toggle(id) {
    if (shown === id) { setShown(null); return; }
    if (!opened[id]) {
      try { setOpened({ ...opened, [id]: await api(`/answers/${id}`) }); } catch (e) { setError(e.message); return; }
    }
    setShown(id);
  }
  async function unsave(id) {
    await api("/bookmarks", { query_id: id, saved: false });
    setList(list.filter((b) => b.query_id !== id));
    if (shown === id) setShown(null);
  }

  return (
    <SitePage kicker="Your account" title="Saved" accent="answers">
      {error && <p className="sp-err" role="alert">{error}</p>}
      {list && list.length === 0 && <p>Nothing saved yet. Under an answer, <b>☆ Save</b> keeps it here.{" "}
        <Link to="/research">Ask a question</Link></p>}
      {list && list.map((b) => (
        <div key={b.query_id} className="sv-item">
          <div className="sv-head">
            <button className="sv-open" onClick={() => toggle(b.query_id)} aria-expanded={shown === b.query_id}>
              <span className="sv-q">{b.question}</span>
              <span className="sv-meta">{STATUS[b.status] || b.status} · asked {b.asked_at.slice(0, 10)} · saved {b.saved_at.slice(0, 10)}</span>
            </button>
            <button className="sv-remove" onClick={() => unsave(b.query_id)} aria-label="Remove from saved answers">★ Saved</button>
          </div>
          {shown === b.query_id && opened[b.query_id] &&
            <Answer a={opened[b.query_id]} onOpen={(chunkId, quote) => setPassage({ chunkId, quote })} />}
        </div>
      ))}
      <PassagePanel open={passage} onClose={() => setPassage(null)} />
    </SitePage>
  );
}
