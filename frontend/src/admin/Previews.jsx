// Previews (Edwin, SPEC 11, 2026-11-20): every screen a visitor sees only when something goes wrong or loads, side
// by side, for the team to check them. They are the real components and pages, in the chosen appearance (Settings);
// the 401 and 403 pages come from the server itself (/admin-preview/...).
import { useEffect, useState } from "react";
import ErrorPage from "../components/ErrorPage.jsx";
import Loader from "../components/Loader.jsx";
import v from "../assets/splash/v.webp";
import vGold from "../assets/splash/v-gold.webp";
import scales from "../assets/splash/scales.webp";
import network from "../assets/splash/network.webp";

// The loading screen of index.html again, full screen, then it fades out like on a real visit (2.4 s + fade).
function Splash({ onDone }) {
  const [out, setOut] = useState(false);
  useEffect(() => {
    const a = setTimeout(() => setOut(true), 2400), b = setTimeout(onDone, 3000);
    return () => { clearTimeout(a); clearTimeout(b); };
  }, [onDone]);
  return (
    <div id="splash" className={out ? "out" : ""} role="status" aria-label="Loading Verdicta (preview)" onClick={onDone}>
      <div className="sl-wrap">
        <div className="sl-stage" aria-hidden="true">
          <i className="sl-halo" />
          <img className="sl-v" src={v} alt="" /><img className="sl-vgold" src={vGold} alt="" />
          <img className="sl-scales" src={scales} alt="" /><img className="sl-net" src={network} alt="" />
          <i className="sl-shine" />
        </div>
        <p className="sl-name" aria-hidden="true">{"VERDICTA".split("").map((ch, i) => <span key={i}>{ch}</span>)}</p>
        <p className="sl-tag">Verified case-law research</p>
        <div className="sl-bar"><i /></div>
      </div>
    </div>
  );
}

function Boom() {
  throw new Error("Preview: a page that crashes on purpose");
}

function Frame({ title, note, children }) {
  return (
    <figure className="pv-card">
      <div className="pv-frame"><div className="pv-inner">{children}</div></div>
      <figcaption><b>{title}</b><span>{note}</span></figcaption>
    </figure>
  );
}

export default function Previews() {
  const [splash, setSplash] = useState(false);
  const [crash, setCrash] = useState(false);
  return (
    <>
      <h2>Page <em>previews</em></h2>
      <p className="ad-lead">The screens a visitor sees only while the site loads or when something goes wrong, as they
        really look, in the appearance chosen in Settings.</p>

      <div className="pv-actions">
        <button onClick={() => setSplash(true)}>Play the loading screen</button>
        <button className="light" onClick={() => setCrash(true)}>Crash this page for real</button>
        <span className="muted">After the crash page, "Try again" reloads the site.</span>
      </div>
      {splash && <Splash onDone={() => setSplash(false)} />}
      {crash && <Boom />}

      <div className="pv-grid">
        <Frame title="Loading inside a page" note="components/Loader.jsx: admin pages, plans, the passage drawer">
          <div className="pv-loader"><Loader /></div>
        </Frame>
        <Frame title="Page not found (404)" note="any address that does not exist">
          <ErrorPage kind="notFound" />
        </Frame>
        <Frame title="Something went wrong" note="a page that crashed (the button above shows it for real)">
          <ErrorPage kind="crashed" />
        </Frame>
        <Frame title="Verdicta cannot be reached" note="the server does not answer when the page starts">
          <ErrorPage kind="offline" />
        </Frame>
        <Frame title="401 Please log in" note="the server's own page: /admin while logged out">
          <iframe src="/admin-preview/401" title="401 preview" />
        </Frame>
        <Frame title="403 Administrators only" note="the server's own page: /admin for a visitor's account">
          <iframe src="/admin-preview/403" title="403 preview" />
        </Frame>
      </div>
    </>
  );
}
