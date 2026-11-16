// The plans panel of the chat (Edwin, 2026-11-16): the account's plan, how many questions are left today, Free vs
// Paid, and Upgrade or Cancel, without leaving the chat. Opened from the chat (and from Joe's account menu).
// Props: open, onClose(), onChange(me) after a cancel, so the chat can show the new plan at once.
// Escape, the × button or a click outside closes it. Upgrading goes to Stripe's page; Stripe sends the person back
// to /pricing, which confirms the payment with the server (pages/Pricing.jsx).
import { useEffect, useRef } from "react";
import { PlanAction, PlanCards, usePlans } from "./Plans.jsx";

export default function PlansDialog({ open, onClose, onChange }) {
  const p = usePlans();
  const box = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    p.setMessage(""); p.setError("");
    p.load().catch(() => {});                       // fresh numbers each time it opens
    box.current?.focus();
    const esc = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [open]);

  if (!open) return null;
  async function cancel() {
    const m = await p.cancel();
    if (m && onChange) onChange(m);
  }
  return (
    <div className="pl-backdrop" onClick={onClose}>
      <div className="pl-dialog" role="dialog" aria-modal="true" aria-labelledby="pl-title" tabIndex={-1} ref={box}
           onClick={(e) => e.stopPropagation()}>
        <button className="pl-close" onClick={onClose} aria-label="Close">×</button>
        <span className="pl-kicker">Your plan</span>
        <h2 id="pl-title">Plans and <em>usage</em></h2>
        {p.account?.user && <p className="pl-dim">{p.account.user.email}</p>}
        {p.message && <p className="pl-ok" role="status">{p.message}</p>}
        {p.error && <p className="pl-err" role="alert">{p.error}</p>}
        <PlanCards info={p.info} account={p.account} />
        <div className="pl-actions"><PlanAction p={{ ...p, cancel }} onNavigate={onClose} /></div>
        <p className="pl-note">Test mode: no real money. Pay with Stripe's test card 4242 4242 4242 4242.</p>
      </div>
    </div>
  );
}
