// The plans, shared by the pricing page (pages/Pricing.jsx) and the plans panel of the chat (PlansDialog.jsx)
// (Edwin, 2026-11-16). One copy of the logic, so the page and the panel always say the same thing.
// - usePlans(): loads GET /api/billing (payments on, price, daily limits) and GET /api/me (the account and its plan),
//   and does the two actions: upgrade (Stripe's own page: the card is never typed on ours) and cancel.
// - PlanCards: Free and Paid side by side, the account's plan marked, and how many questions are left today.
// - PlanAction: the one button that fits the account (sign up, upgrade, cancel, or nothing for an administrator).
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, me } from "../api.js";
import "./plans.css";
import Loader from "./Loader.jsx";   // the animated logo while the plan loads (Edwin)

export function usePlans() {
  const [info, setInfo] = useState(null);        // enabled, price_label, free_daily, paid_daily
  const [account, setAccount] = useState(null);  // user, plan {plan, daily_limit, left_today}, unlimited
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => Promise.all([api("/billing"), me()]).then(([b, m]) => { setInfo(b); setAccount(m); return m; });
  useEffect(() => { load().catch((e) => setError(e.message)); }, []);

  async function go(path, after) {
    setBusy(true); setError(""); setMessage("");
    try {
      const r = await api(path, {});
      if (r.url) { window.location.assign(r.url); return null; }   // Stripe's payment page; we come back to /pricing
      setMessage(after);
      return await load();
    } catch (e) { setError(e.message); return null; }
    finally { setBusy(false); }
  }
  return {
    info, account, message, error, busy, load, setMessage, setError,
    upgrade: () => go("/billing/checkout"),
    cancel: () => go("/billing/cancel", "Subscription cancelled: your account is back on the free plan."),
  };
}

function Usage({ plan }) {
  const used = plan.daily_limit - plan.left_today;
  const share = Math.min(1, used / Math.max(1, plan.daily_limit));
  return (
    <div className="pl-usage">
      <div className="pl-usage-top"><span>Today</span><b>{plan.left_today} of {plan.daily_limit} questions left</b></div>
      <div className="pl-bar" role="progressbar" aria-valuemin={0} aria-valuemax={plan.daily_limit} aria-valuenow={used}
           aria-label="Questions used today"><i style={{ width: `${share * 100}%` }} /></div>
      <span className="pl-dim">The day starts again at midnight, Beirut time.</span>
    </div>
  );
}

export function PlanCards({ info, account }) {
  const plan = account?.plan;                    // only for a 'user' account
  const card = (key, name, price, perDay, lines) => (
    <div className={`pl-card ${plan?.plan === key ? "pl-mine" : ""}`}>
      {plan?.plan === key && <span className="pl-badge">Your plan</span>}
      <h3>{name}</h3>
      <p className="pl-price">{price}</p>
      <ul><li><b>{perDay}</b> questions a day</li>{lines.map((l) => <li key={l}>{l}</li>)}</ul>
    </div>
  );
  return (
    <>
      {account?.unlimited && <p className="pl-admin">You are an administrator: no plan and no limit.</p>}
      {plan && <Usage plan={plan} />}
      <div className="pl-cards">
        {card("free", "Free", "$0", info ? info.free_daily : "…", ["Saved chats and history", "Every answer verified"])}
        {card("paid", "Paid", info ? info.price_label : "…", info ? info.paid_daily : "…",
              ["Everything in Free", "Cancel at any time"])}
      </div>
    </>
  );
}

export function PlanAction({ p, onNavigate }) {
  const { info, account, busy } = p;
  if (!info || !account) return <Loader small />;
  if (!account.user) return <p><Link to="/signup" onClick={onNavigate}>Sign up</Link> (free) to keep your questions;
    you can upgrade after.</p>;
  if (account.unlimited) return null;
  if (!info.enabled) return <p className="pl-dim">Payments are not set up on this site yet. An administrator can still
    switch an account to the paid plan.</p>;
  if (account.plan?.plan === "paid") return <button className="pl-btn pl-quiet" disabled={busy} onClick={p.cancel}>
    {busy ? "Cancelling…" : "Cancel the paid plan"}</button>;
  return <button className="pl-btn" disabled={busy} onClick={p.upgrade}>
    {busy ? "Opening Stripe…" : `Upgrade to Paid · ${info.price_label}`}</button>;
}
