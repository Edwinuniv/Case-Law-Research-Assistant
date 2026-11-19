// The pricing page (Edwin, SPEC 11, 2026-11-15): Free or Paid, and paying with Stripe in TEST mode (no real money).
// The plans themselves (cards, usage, the button) are shared with the chat's plans panel: components/Plans.jsx.
// This page also does the one thing only it does: back from Stripe with ?session_id=..., it asks the server to
// confirm the payment with Stripe (POST /api/billing/confirm) before the account becomes paid. Confirming twice
// changes nothing.
import { useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api.js";
import { PlanAction, PlanCards, usePlans } from "../components/Plans.jsx";
import SitePage from "./SitePage.jsx";

export default function Pricing() {
  const [params, setParams] = useSearchParams();
  const p = usePlans();

  useEffect(() => {
    const sessionId = params.get("session_id");
    if (sessionId) {
      api("/billing/confirm", { session_id: sessionId })
        .then(() => p.setMessage("Payment received: your account is now on the paid plan."))
        .catch((e) => p.setError(e.message))
        .finally(() => { p.load().catch(() => {}); setParams({}, { replace: true }); });
    }
    if (params.get("cancelled")) p.setMessage("Payment cancelled: nothing was charged and your plan did not change.");
  }, []);

  return (
    <SitePage kicker="Plans" title="Free or" accent="Paid">
      <div className="sp-card sp-note">
        <strong>Test mode: no real money.</strong> Payments go through Stripe's test mode, for this student project. To try
        it, choose Card and pay with Stripe's test card 4242 4242 4242 4242, any future date and any three digits.
      </div>
      {p.message && <p className="sp-ok" role="status">{p.message} <Link to="/research">Back to the chat</Link></p>}
      {p.error && <p className="sp-err" role="alert">{p.error}</p>}
      <PlanCards info={p.info} account={p.account} />
      <div className="pl-actions"><PlanAction p={p} /></div>
      <p className="sp-small" style={{ marginTop: 18 }}>Without an account: one question per browser session. See the{" "}
        <Link to="/terms">terms of use</Link> and the <Link to="/privacy">privacy policy</Link>.</p>
    </SitePage>
  );
}
