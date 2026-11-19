// The error pages (Edwin, SPEC 11, 2026-11-19): a page that does not exist, a page that crashed, or a server
// that does not answer. Plain words only: never the technical error, a file name or what the server said,
// so the page tells an attacker nothing. The real error is in the browser console (crash) or the server's log.
import { Component } from "react";
import Logo from "./Logo.jsx";
import "./errors.css";

const KINDS = {
  notFound: { code: "404", title: "This page does not exist",
    text: "The address may be mistyped, or the page has moved. Nothing is wrong with your account." },
  crashed: { code: "Oops", title: "Something went wrong on this page",
    text: "It is not your fault. Reload the page; if it happens again, tell us on the contact page." },
  offline: { code: "…", title: "Verdicta cannot be reached right now",
    text: "Check your internet connection, then try again in a moment." },
};

export default function ErrorPage({ kind = "notFound", inApp = false }) {   // inApp: under the site's own header
  const k = KINDS[kind];
  // plain links (not React Router): after a crash or with no server, a full reload is the safe way back
  return (
    <div className={inApp ? "er er-in-app" : "er"} role={kind === "notFound" ? undefined : "alert"}>
      <div className="er-glow" aria-hidden="true" />
      {!inApp && <a href="/" className="er-brand"><Logo /> Verdicta</a>}
      <p className="er-code" aria-hidden="true">{k.code}</p>
      <h1>{k.title}</h1>
      <p className="er-text">{k.text}</p>
      <div className="er-actions">
        {kind === "notFound"
          ? <a className="er-btn" href="/research">Ask a question</a>
          : <button className="er-btn" onClick={() => window.location.reload()}>Try again</button>}
        <a className="er-link" href="/">Back to the home page</a>
      </div>
    </div>
  );
}

// Catches a crash in any page below it and shows the "crashed" page instead of a blank screen.
export class ErrorBoundary extends Component {
  state = { crashed: false };
  static getDerivedStateFromError() { return { crashed: true }; }
  componentDidCatch(error) { console.error(error); }     // the detail stays in the console, never on the page
  render() { return this.state.crashed ? <ErrorPage kind="crashed" /> : this.props.children; }
}
