// Tools of the chat (Edwin, SPEC 11, 2026-11-21, like the screenshots Edwin sent): copy a message, switch between the
// versions of an edited question, and a navigator on the right (one mark per question, the one in view highlighted)
// with a button back to the bottom.
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import "./chattools.css";

const CopyIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="8" width="12" height="12" rx="3" />
    <path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" /></svg>
);
const CheckIcon = () => <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>;
export const PenIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20h4L19 9l-4-4L4 16v4z" /><path d="M13.5 6.5l4 4" />
    <path d="M14 20h6" /></svg>
);

export const PinIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 4h6l-1 6 4 3v2H6v-2l4-3-1-6z" /><path d="M12 15v6" /></svg>
);

export function CopyButton({ text, label = "Copy" }) {
  const [done, setDone] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
    } catch {                                        // an older browser or a page without clipboard permission
      const t = document.createElement("textarea");
      t.value = text; document.body.appendChild(t); t.select(); document.execCommand("copy"); t.remove();
    }
    setDone(true);
    setTimeout(() => setDone(false), 1500);
  }
  return (
    <button type="button" className="ct-icon" onClick={copy} aria-label={done ? "Copied" : label} title={done ? "Copied" : label}>
      {done ? <CheckIcon /> : <CopyIcon />}
    </button>
  );
}

export function Versions({ index, count, onPick }) {
  if (count < 2) return null;
  return (
    <span className="ct-versions" aria-label={`Version ${index + 1} of ${count}`}>
      <button type="button" onClick={() => onPick(index - 1)} disabled={index === 0} aria-label="Previous version">‹</button>
      <span>{index + 1} / {count}</span>
      <button type="button" onClick={() => onPick(index + 1)} disabled={index === count - 1} aria-label="Next version">›</button>
    </span>
  );
}

// ids: the questions on screen, in order; each question's element has id `q-<id>`.
export function Navigator({ ids, titles }) {
  const [active, setActive] = useState(null);
  const [away, setAway] = useState(false);          // scrolled up from the bottom
  useEffect(() => {
    function look() {
      const middle = window.innerHeight * 0.4;
      let current = ids[0] ?? null;
      for (const id of ids) {
        const el = document.getElementById(`q-${id}`);
        if (el && el.getBoundingClientRect().top < middle) current = id;
      }
      setActive(current);
      setAway(document.documentElement.scrollHeight - window.scrollY - window.innerHeight > 300);
    }
    look();
    window.addEventListener("scroll", look, { passive: true });
    window.addEventListener("resize", look);
    return () => { window.removeEventListener("scroll", look); window.removeEventListener("resize", look); };
  }, [ids.join(",")]);

  return createPortal(                            // in <body>: a parent with a transform would move a fixed element
    <>
      {ids.length > 1 && (
        <nav className="ct-nav" aria-label="Questions in this chat">
          {ids.map((id, k) => (
            <button key={id} type="button" className={id === active ? "on" : ""} title={titles[k]}
                    aria-label={`Go to question ${k + 1}: ${titles[k]}`}
                    onClick={() => document.getElementById(`q-${id}`)?.scrollIntoView({ behavior: "smooth", block: "start" })} />
          ))}
        </nav>
      )}
      {away && (
        <button type="button" className="ct-bottom" aria-label="Go to the bottom"
                onClick={() => window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "smooth" })}>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6" /></svg>
        </button>
      )}
    </>,
    document.body,
  );
}
