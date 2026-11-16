"""Paying for the paid plan in Stripe TEST mode (SPEC section 11, 2026-11-15). Written from the rule, before the code.
Stripe is never called: app/billing.py's calls to Stripe are replaced by fakes. The webhook tests sign their events
with a test secret exactly as Stripe does, so the real signature check runs."""
import hashlib
import hmac
import json
import time
import pytest
from tests.test_api_research import c, csrf, ask   # noqa: F401  (c is the fixture)
from tests.test_plans import reader, admin, READER  # noqa: F401  (fixtures)

SECRET = "whsec_test_secret"


@pytest.fixture
def stripe_on(monkeypatch):
    """Payments set up with test keys; the calls to Stripe are fakes that remember what they were asked."""
    from app import billing
    monkeypatch.setattr(billing, "SECRET_KEY", "sk_test_123")
    monkeypatch.setattr(billing, "PRICE_ID", "price_123")
    monkeypatch.setattr(billing, "WEBHOOK_SECRET", SECRET)
    calls = {"checkout": [], "cancel": [], "sessions": {}}

    def create_checkout(user_id, email, base_url):
        calls["checkout"].append((user_id, email))
        return "https://checkout.stripe.com/c/pay/cs_test_1"
    monkeypatch.setattr(billing, "create_checkout", create_checkout)
    monkeypatch.setattr(billing, "fetch_session", lambda sid: calls["sessions"][sid])
    monkeypatch.setattr(billing, "cancel_subscription", lambda sub: calls["cancel"].append(sub))
    return calls


def session(user_id, sid="cs_test_1", status="complete", paid="paid"):
    """A Checkout session as Stripe returns it (only the fields we read)."""
    return {"id": sid, "status": status, "payment_status": paid, "client_reference_id": str(user_id),
            "customer": "cus_1", "subscription": "sub_1"}


def post(client, path, body=None):
    return client.post(path, json=body or {}, headers=csrf(client))


def plan_of(clean_db, user_id):
    with clean_db.connect() as con:
        return con.execute("SELECT plan, stripe_customer_id, stripe_subscription_id FROM users WHERE id = %s",
                           (user_id,)).fetchone()


def plan_changes(clean_db, user_id):
    with clean_db.connect() as con:
        return [r["detail"] for r in con.execute("SELECT detail FROM user_log WHERE user_id = %s AND event = "
                                                 "'plan_change' ORDER BY id", (user_id,))]


def signed(client, event, secret=SECRET):
    """Sends an event to the webhook with Stripe's signature header: t=<time>,v1=HMAC-SHA256(secret, '<t>.<body>')."""
    body = json.dumps(event)
    t = int(time.time())
    sig = hmac.new(secret.encode(), f"{t}.{body}".encode(), hashlib.sha256).hexdigest()
    return client.post("/api/billing/webhook", content=body,
                       headers={"Stripe-Signature": f"t={t},v1={sig}", "Content-Type": "application/json"})


def event(kind, obj, eid="evt_1"):
    return {"id": eid, "object": "event", "type": kind, "data": {"object": obj}}


# ---- (1)-(2) test mode only, off unless set up ----
def test_payments_are_off_without_the_keys(c, reader, monkeypatch):
    from app import billing
    monkeypatch.setattr(billing, "SECRET_KEY", "")          # whatever the developer's .env holds
    monkeypatch.setattr(billing, "PRICE_ID", "")
    assert c.get("/api/billing").json()["enabled"] is False
    assert post(c, "/api/billing/checkout").status_code == 404


@pytest.mark.parametrize("key", ["sk_live_123", "rk_live_123"])
def test_a_live_key_is_refused(c, reader, stripe_on, monkeypatch, key):
    from app import billing
    monkeypatch.setattr(billing, "SECRET_KEY", key)
    assert c.get("/api/billing").json()["enabled"] is False
    assert post(c, "/api/billing/checkout").status_code == 404


def test_a_restricted_test_key_is_accepted(c, reader, stripe_on, monkeypatch):     # Edwin's key (2026-11-16)
    from app import billing
    monkeypatch.setattr(billing, "SECRET_KEY", "rk_test_123")
    assert c.get("/api/billing").json()["enabled"] is True
    assert post(c, "/api/billing/checkout").status_code == 200


def test_the_pricing_page_gets_the_limits_and_the_price(c, stripe_on):
    info = c.get("/api/billing").json()
    assert info["enabled"] is True and info["free_daily"] == 10 and info["paid_daily"] == 100 and info["price_label"]


# ---- (4) paying ----
def test_a_free_account_gets_the_address_of_stripes_page(c, reader, stripe_on):
    r = post(c, "/api/billing/checkout")
    assert r.status_code == 200 and r.json()["url"].startswith("https://checkout.stripe.com/")
    assert stripe_on["checkout"] == [(reader, READER)]


def test_checkout_needs_the_csrf_token_and_an_account(c, stripe_on):
    assert c.post("/api/billing/checkout", json={}).status_code == 403          # no token
    assert post(c, "/api/billing/checkout").status_code == 401                  # a visitor without an account
    assert stripe_on["checkout"] == []


def test_an_administrator_has_nothing_to_pay(admin, stripe_on):
    assert post(admin, "/api/billing/checkout").status_code == 400
    assert stripe_on["checkout"] == []


def test_coming_back_paid_makes_the_account_paid(c, reader, stripe_on, clean_db):
    stripe_on["sessions"]["cs_test_1"] = session(reader)
    assert post(c, "/api/billing/confirm", {"session_id": "cs_test_1"}).status_code == 200
    row = plan_of(clean_db, reader)
    assert (row["plan"], row["stripe_customer_id"], row["stripe_subscription_id"]) == ("paid", "cus_1", "sub_1")
    assert plan_changes(clean_db, reader) == [{"from": "free", "to": "paid", "by": "stripe"}]
    assert c.get("/api/me").json()["plan"]["daily_limit"] == 100


def test_confirming_twice_changes_the_plan_once(c, reader, stripe_on, clean_db):
    stripe_on["sessions"]["cs_test_1"] = session(reader)
    post(c, "/api/billing/confirm", {"session_id": "cs_test_1"})
    post(c, "/api/billing/confirm", {"session_id": "cs_test_1"})
    assert len(plan_changes(clean_db, reader)) == 1


@pytest.mark.parametrize("status,paid", [("open", "unpaid"), ("complete", "unpaid"), ("expired", "unpaid")])
def test_a_session_not_paid_changes_nothing(c, reader, stripe_on, clean_db, status, paid):
    stripe_on["sessions"]["cs_test_1"] = session(reader, status=status, paid=paid)
    assert post(c, "/api/billing/confirm", {"session_id": "cs_test_1"}).status_code == 400
    assert plan_of(clean_db, reader)["plan"] == "free" and plan_changes(clean_db, reader) == []


def test_another_accounts_session_changes_nothing(c, reader, stripe_on, clean_db):
    stripe_on["sessions"]["cs_test_1"] = session(reader + 1000)           # paid, but for someone else
    assert post(c, "/api/billing/confirm", {"session_id": "cs_test_1"}).status_code == 403
    assert plan_of(clean_db, reader)["plan"] == "free"


# ---- (5) the webhook ----
def test_a_signed_completed_checkout_makes_the_account_paid(c, reader, stripe_on, clean_db):
    assert signed(c, event("checkout.session.completed", session(reader))).status_code == 200
    assert plan_of(clean_db, reader)["plan"] == "paid"
    assert plan_changes(clean_db, reader) == [{"from": "free", "to": "paid", "by": "stripe"}]


def test_a_forged_or_unsigned_event_changes_nothing(c, reader, stripe_on, clean_db):
    assert signed(c, event("checkout.session.completed", session(reader)), secret="whsec_wrong").status_code == 400
    assert c.post("/api/billing/webhook", content=json.dumps(event("checkout.session.completed", session(reader))),
                  headers={"Content-Type": "application/json"}).status_code == 400
    assert plan_of(clean_db, reader)["plan"] == "free"


def test_the_same_event_twice_changes_the_plan_once(c, reader, stripe_on, clean_db):
    e = event("checkout.session.completed", session(reader))
    signed(c, e)
    signed(c, e)
    assert len(plan_changes(clean_db, reader)) == 1


def test_a_deleted_subscription_makes_the_account_free_again(c, reader, stripe_on, clean_db):
    signed(c, event("checkout.session.completed", session(reader)))
    assert signed(c, event("customer.subscription.deleted", {"id": "sub_1", "object": "subscription"},
                           eid="evt_2")).status_code == 200
    assert plan_of(clean_db, reader)["plan"] == "free"
    assert plan_changes(clean_db, reader)[-1] == {"from": "paid", "to": "free", "by": "stripe"}


def test_without_a_webhook_secret_the_webhook_is_off(c, reader, stripe_on, monkeypatch):
    from app import billing
    monkeypatch.setattr(billing, "WEBHOOK_SECRET", "")
    assert signed(c, event("checkout.session.completed", session(reader))).status_code == 404


# ---- (6) cancelling ----
def test_cancelling_stops_the_subscription_and_makes_the_account_free(c, reader, stripe_on, clean_db):
    stripe_on["sessions"]["cs_test_1"] = session(reader)
    post(c, "/api/billing/confirm", {"session_id": "cs_test_1"})
    assert post(c, "/api/billing/cancel").status_code == 200
    assert stripe_on["cancel"] == ["sub_1"]
    row = plan_of(clean_db, reader)
    assert row["plan"] == "free" and row["stripe_subscription_id"] is None
    assert plan_changes(clean_db, reader)[-1] == {"from": "paid", "to": "free", "by": "stripe"}


def test_a_free_account_has_nothing_to_cancel(c, reader, stripe_on):
    assert post(c, "/api/billing/cancel").status_code == 400
    assert stripe_on["cancel"] == []
