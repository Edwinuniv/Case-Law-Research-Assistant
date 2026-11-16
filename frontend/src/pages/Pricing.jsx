// The pricing page (Edwin, SPEC 11, 2026-11-15): Free or Paid, and paying with Stripe in TEST mode (no real money).
// - A visitor is sent to sign up first; an administrator has no plan and no limit.
// - "Upgrade" asks the server for Stripe's payment page (POST /api/billing/checkout) and goes there: the card number
//   is typed on Stripe's page, never on ours.
// - Back from Stripe with ?session_id=..., the server asks Stripe whether that payment is complete
//   (POST /api/billing/confirm) before the account becomes paid. Confirming twice changes nothing.
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, me } from "../api.js";
import SitePage from "./SitePage.jsx";

export default function Pricing() {
  const [params, setParams] = useSearchParams();
  const [info, setInfo] = useState(null);        // GET /api/billing: enabled, price_label, free_daily, paid_daily
  const [account, setAccount] = useState(null);  // GET /api/me: user, plan, unlimited
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => Promise.all([api("/billing"), me()]).then(([b, m]) => { setInfo(b); setAccount(m); });

  useEffect(() => {
    const sessionId = params.get("session_id");
    const confirm = sessionId
      ? api("/billing/confirm", { session_id: sessionId })
          .then(() => setMessage("Payment received: your account is now on the paid plan."))
          .catch((e) => setError(e.message))
      : Promise.resolve();
    if (params.get("cancelled")) setMessage("Payment cancelled: nothing was charged and your plan did not change.");
    confirm.finally(() => { load().catch((e) => setError(e.message)); if (sessionId) setParams({}, { replace: true }); });
  }, []);

  async function go(path, after) {
    setBusy(true); setError("");
    try {
      const r = await api(path, {});
      if (r.url) window.location.assign(r.url);       // Stripe's own payment page
      else { setMessage(after); await load(); }
    } catch (e) { setError(e.message); }
    setBusy(false);
  }

  const user = account?.user;
  const plan = account?.plan?.plan;                   // 'free' or 'paid' for a user account; null otherwise
  let action;
  if (!info) action = <p className="sp-small">Loading…</p>;
  else if (!user) action = <p><Link to="/signup">Sign up</Link> (free) to keep your questions; you can upgrade after.</p>;
  else if (account.unlimited) action = <p>You are an administrator: no plan and no limit.</p>;
  else if (!info.enabled) action = <p className="sp-small">Payments are not set up on this site yet. An administrator can
    still switch an account to the paid plan.</p>;
  else if (plan === "paid") action = <div className="sp-form"><p>Your account is on the <strong>paid plan</strong>.</p>
    <button disabled={busy} onClick={() => go("/billing/cancel", "Subscription cancelled: your account is back on the free plan.")}>
      Cancel the paid plan</button></div>;
  else action = <div className="sp-form"><button disabled={busy} onClick={() => go("/billing/checkout")}>
    {busy ? "Opening Stripe…" : `Upgrade to Paid · ${info.price_label}`}</button></div>;

  return (
    <SitePage kicker="Plans" title="Free or" accent="Paid">
      <div className="sp-card sp-note">
        <strong>Test mode: no real money.</strong> Payments go through Stripe's test mode, for this student project. To try
        it, pay with Stripe's test card 4242 4242 4242 4242, any future date and any three digits.
      </div>
      {message && <p className="sp-ok" role="status">{message}</p>}
      {error && <p className="sp-err" role="alert">{error}</p>}

      <div className="pr-plans">
        <div className={`sp-card pr-plan ${plan === "free" ? "pr-mine" : ""}`}>
          <h2>Free</h2>
          <p className="pr-price">$0</p>
          <ul>
            <li>{info ? info.free_daily : 10} questions a day</li>
            <li>Saved chats and question history</li>
            <li>Every answer verified, every citation checked</li>
          </ul>
        </div>
        <div className={`sp-card pr-plan ${plan === "paid" ? "pr-mine" : ""}`}>
          <h2>Paid</h2>
          <p className="pr-price">{info ? info.price_label : ""}</p>
          <ul>
            <li>{info ? info.paid_daily : 100} questions a day</li>
            <li>Everything in Free</li>
            <li>Cancel at any time: back to Free at once</li>
          </ul>
        </div>
      </div>
      {action}
      <p className="sp-small">The day starts again at midnight, Beirut time. Without an account: one question per browser
        session. See the <Link to="/terms">terms of use</Link> and the <Link to="/privacy">privacy policy</Link>.</p>
    </SitePage>
  );
}
