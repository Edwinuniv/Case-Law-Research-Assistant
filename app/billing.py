"""Paying for the paid plan with Stripe, in TEST mode only (Edwin, SPEC section 11, 2026-11-15).

How a payment goes: the account asks for a Checkout session (create_checkout); the browser goes to Stripe's own page,
so card numbers never reach our server; Stripe sends the person back to /pricing?session_id=..., and the server asks
Stripe for that session (fetch_session) before believing it (apply_session). Stripe can also tell us by a webhook,
whose signature is checked (parse_event). Only Stripe's customer id and subscription id are kept on the account.

The four functions that talk to Stripe are small on purpose: the tests replace them with fakes (tests/test_billing.py)."""
import os

import stripe

from app import config, db, emails, logs, notices  # noqa: F401  (config loads .env before the keys below are read)

SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "").strip()       # sk_test_ or rk_test_ only (a live key: payments off)
PRICE_ID = os.environ.get("STRIPE_PRICE_ID", "").strip()           # the monthly price made in the Stripe dashboard
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()   # optional: whsec_...
DEFAULT_PRICE_LABEL = "$15 a month"          # the Stripe test price (price_1...); the page said $5 live (2026-11-21)


def price_label():
    """What the plans page shows for the paid plan: PAID_PRICE_LABEL if set, else the Stripe price."""
    return os.environ.get("PAID_PRICE_LABEL", "").strip() or DEFAULT_PRICE_LABEL
SITE_URL = os.environ.get("SITE_URL", "").strip().rstrip("/")      # where Stripe sends people back; empty: this site


def enabled():
    """Payments are on only with a TEST key, secret (sk_test_) or restricted (rk_test_), and a price
    (SPEC 11: test mode only, no real money)."""
    return SECRET_KEY.startswith(("sk_test_", "rk_test_")) and bool(PRICE_ID)


# ---------------- the calls to Stripe ----------------
def create_checkout(user_id, email, base_url):
    """A Stripe Checkout session for the monthly subscription; returns the address of Stripe's payment page.
    Which payment methods the page offers (card only, no Cash App) is set in the Stripe dashboard, not here:
    Stripe refuses payment_method_types since its newer API (README; AI_LOG 2026-11-16)."""
    s = stripe.checkout.Session.create(
        api_key=SECRET_KEY, mode="subscription", line_items=[{"price": PRICE_ID, "quantity": 1}],
        client_reference_id=str(user_id), customer_email=email,
        success_url=f"{base_url}/pricing?session_id={{CHECKOUT_SESSION_ID}}",   # Stripe fills in the session id
        cancel_url=f"{base_url}/pricing?cancelled=1")
    return s.url


def fetch_session(session_id):
    """The Checkout session as Stripe has it (never as the browser says it is), as a plain dict: since stripe 17 a
    StripeObject is not a dict (no .get), found by tests/test_billing.py."""
    return stripe.checkout.Session.retrieve(session_id, api_key=SECRET_KEY).to_dict()


def cancel_subscription(subscription_id):
    stripe.Subscription.cancel(subscription_id, api_key=SECRET_KEY)


def parse_event(payload, signature):
    """A webhook event, only if Stripe's signature matches our secret; otherwise ValueError or SignatureVerificationError."""
    return stripe.Webhook.construct_event(payload, signature, WEBHOOK_SECRET).to_dict()     # a plain dict, as above


# ---------------- what a payment changes ----------------
def switch(user_id, plan, customer=None, subscription=None):
    """Sets the plan and Stripe's ids; writes plan_change only if the plan really changed (the same event twice
    changes nothing the second time). Returns (old plan, why it was refused or None)."""
    old, why = db.set_plan(user_id, plan)
    if why:
        return old, why
    with db.connect() as con:
        if plan == "paid":
            con.execute("UPDATE users SET stripe_customer_id = %s, stripe_subscription_id = %s WHERE id = %s",
                        (customer, subscription, user_id))
        else:
            con.execute("UPDATE users SET stripe_subscription_id = NULL WHERE id = %s", (user_id,))
    if old != plan:
        logs.log_user(user_id, "plan_change", {"from": old, "to": plan, "by": "stripe"})
        notify_plan(user_id, plan)
    return old, None


def notify_plan(user_id, plan):
    """Emails the account its new plan and daily limit (SPEC 11, 2026-11-20), by Stripe or an administrator."""
    from app import api                        # here, not at the top: app/api.py is loaded first
    with db.connect() as con:
        email = con.execute("SELECT email FROM users WHERE id = %s", (user_id,)).fetchone()["email"]
    emails.plan_changed(email, plan, api.daily_limit(plan))
    notices.add(user_id, "plan_changed", f"Your plan is now {'Paid' if plan == 'paid' else 'Free'}: "
                f"{api.daily_limit(plan)} questions a day.", "/pricing")


def is_paid(session):
    return session.get("status") == "complete" and session.get("payment_status") == "paid"


def apply_session(session):
    """A completed and paid Checkout session makes its account paid. Returns why not, or None."""
    if not is_paid(session):
        return "not paid"
    _, why = switch(int(session["client_reference_id"]), "paid", session.get("customer"), session.get("subscription"))
    return why


def apply_deleted_subscription(subscription_id):
    """Stripe ended the subscription: its account goes back to free."""
    with db.connect() as con:
        row = con.execute("SELECT id FROM users WHERE stripe_subscription_id = %s", (subscription_id,)).fetchone()
    if row:
        switch(row["id"], "free")


def subscription_of(user_id):
    with db.connect() as con:
        row = con.execute("SELECT plan, stripe_subscription_id FROM users WHERE id = %s", (user_id,)).fetchone()
    return row["stripe_subscription_id"] if row and row["plan"] == "paid" else None
