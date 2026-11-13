// "Continue with Google" on the sign-up and login pages (Yasser, SPEC 11, 2026-11-13).
// Google's own button (Google Identity Services) opens Google's window; Google gives back an ID token, and we send it
// to POST /api/auth/google, where the server checks it (app/google_auth.py) and logs the account in.
// Shown only when the server gives a client id (GET /api/me -> google_client_id); otherwise nothing is drawn.
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, me } from "../api.js";

let gisLoading = null;            // the Google script is loaded once, whichever page asks first
function loadGoogle() {
  if (window.google?.accounts?.id) return Promise.resolve();
  if (!gisLoading) {
    gisLoading = new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = "https://accounts.google.com/gsi/client";
      s.async = true;
      s.onload = resolve;
      s.onerror = () => { gisLoading = null; reject(new Error("Google could not be reached. Use your email instead.")); };
      document.head.appendChild(s);
    });
  }
  return gisLoading;
}

export default function GoogleButton({ mode, onLogin }) {
  const box = useRef(null);
  const [clientId, setClientId] = useState(null);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    let live = true;
    me().then((d) => live && setClientId(d.google_client_id || null)).catch(() => {});
    return () => { live = false; };
  }, []);

  useEffect(() => {
    if (!clientId) return undefined;
    let live = true;
    loadGoogle().then(() => {
      if (!live || !box.current) return;
      window.google.accounts.id.initialize({
        client_id: clientId,
        context: mode === "signup" ? "signup" : "signin",
        callback: async ({ credential }) => {          // Google's ID token for the account the person chose
          setError("");
          try {
            const data = await api("/auth/google", { credential });
            onLogin(data.user);
            navigate("/research");
          } catch (err) {
            setError(err.message);                     // e.g. "Administrators log in with their password."
          }
        },
      });
      window.google.accounts.id.renderButton(box.current, {
        type: "standard", theme: "filled_black", size: "large", shape: "pill", logo_alignment: "center",
        text: mode === "signup" ? "signup_with" : "continue_with",
        width: Math.min(box.current.offsetWidth || 360, 400),
      });
    }).catch(() => live && setClientId(null));     // Google unreachable (blocked, offline): the email form only
    return () => { live = false; };
  }, [clientId, mode]);

  if (!clientId) return null;
  return (
    <div className="au-google">
      <div className="au-or"><span>or</span></div>
      <div ref={box} className="au-google-btn" />
      {error && <p className="au-error" role="alert">{error}</p>}
    </div>
  );
}
