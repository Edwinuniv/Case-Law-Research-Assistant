// Settings (Edwin, 2026-11-19): a round button at the bottom left of every page opens a small panel where the
// visitor chooses the appearance: dark pages with white sections (the default) or light pages with dark sections.
// The choice is kept in this browser only (localStorage): no account needed, nothing sent to the server.
// index.html applies it before the page is drawn, so there is no flash of the other theme.
import { useEffect, useRef, useState } from "react";

const KEY = "verdicta-theme";

function current() {
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

export default function ThemeSwitch() {
  const [open, setOpen] = useState(false);
  const [theme, setTheme] = useState(current);
  const box = useRef(null);

  useEffect(() => {
    if (!open) return;
    const close = (e) => { if (e.key === "Escape" || (e.type === "mousedown" && !box.current?.contains(e.target))) setOpen(false); };
    document.addEventListener("keydown", close);
    document.addEventListener("mousedown", close);
    return () => { document.removeEventListener("keydown", close); document.removeEventListener("mousedown", close); };
  }, [open]);

  function choose(t) {
    document.documentElement.dataset.theme = t;
    try { localStorage.setItem(KEY, t); } catch { /* private mode: the choice lasts until the page is closed */ }
    setTheme(t);
  }

  const option = (t, title, text) => (
    <button type="button" role="radio" aria-checked={theme === t} className="ts-option" onClick={() => choose(t)}>
      <span className={`ts-pic ts-pic-${t}`} aria-hidden="true"><i /></span>
      <span>{title}<small>{text}</small></span>
    </button>
  );

  return (
    <div className="ts" ref={box}>
      {open && (
        <div className="ts-panel" role="dialog" aria-label="Settings">
          <h2>Settings</h2>
          <p>Saved in this browser only.</p>
          <span className="ts-label" id="ts-appearance">Appearance</span>
          <div className="ts-options" role="radiogroup" aria-labelledby="ts-appearance">
            {option("dark", "Dark", "white sections")}
            {option("light", "Light", "dark sections")}
          </div>
        </div>
      )}
      <button type="button" className="ts-btn" aria-label="Settings" aria-expanded={open} onClick={() => setOpen(!open)}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3.2" />
          <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
        </svg>
      </button>
    </div>
  );
}
