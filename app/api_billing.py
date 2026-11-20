"""The routes of the paid plan, Stripe TEST mode (Edwin, SPEC section 11, 2026-11-15). The Stripe calls are in
app/billing.py. The browser routes check the CSRF token one by one: the webhook cannot, because Stripe's server calls it
(not a browser); Stripe's signature protects it instead."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from stripe import SignatureVerificationError

from app import api, billing

router = APIRouter(prefix="/api/billing")
CSRF = [Depends(api.check_csrf)]


def must_be_on():
    if not billing.enabled():
        raise HTTPException(404, "Payments are not set up on this site.")


def a_user_account(user):
    if user["role"] != "user":
        raise HTTPException(400, "Administrators have no plan and no limit.")


@router.get("")
def info():
    """For the pricing page: are payments on, the price, the two daily limits (from the settings)."""
    return {"enabled": billing.enabled(), "price_label": billing.PRICE_LABEL,
            "free_daily": api.daily_limit("free"), "paid_daily": api.daily_limit("paid")}


@router.post("/checkout", dependencies=CSRF)
def checkout(request: Request, user=Depends(api.require_user)):
    """The address of Stripe's payment page for this free account."""
    must_be_on()
    a_user_account(user)
    if api.needs_verification(user["id"]):            # SPEC 11, 2026-11-20: verified accounts only
        raise HTTPException(403, "Verify your email before choosing the paid plan.")
    if api.plan_info(user["id"])["plan"] == "paid":
        raise HTTPException(400, "This account is already on the paid plan.")
    base = billing.SITE_URL or str(request.base_url).rstrip("/")
    return {"url": billing.create_checkout(user["id"], user["email"], base)}


class Confirm(BaseModel):
    session_id: str


@router.post("/confirm", dependencies=CSRF)
def confirm(body: Confirm, user=Depends(api.require_user)):
    """Back from Stripe: we ask Stripe for the session; only a paid session made for THIS account counts."""
    must_be_on()
    a_user_account(user)
    session = billing.fetch_session(body.session_id)
    if str(session.get("client_reference_id")) != str(user["id"]):
        raise HTTPException(403, "This payment was not made for your account.")
    if billing.apply_session(session):
        raise HTTPException(400, "Stripe says this payment is not complete.")
    return api.plan_info(user["id"])


@router.post("/cancel", dependencies=CSRF)
def cancel(user=Depends(api.require_user)):
    """Cancels the subscription at Stripe and makes the account free at once."""
    must_be_on()
    a_user_account(user)
    subscription = billing.subscription_of(user["id"])
    if not subscription:
        raise HTTPException(400, "This account has no paid subscription to cancel.")
    billing.cancel_subscription(subscription)
    billing.switch(user["id"], "free")
    return api.plan_info(user["id"])


@router.post("/webhook")
async def webhook(request: Request):
    """Stripe's messages. Only with STRIPE_WEBHOOK_SECRET set, and only with Stripe's signature."""
    must_be_on()
    if not billing.WEBHOOK_SECRET:
        raise HTTPException(404, "The webhook is not set up.")
    try:
        event = billing.parse_event(await request.body(), request.headers.get("Stripe-Signature", ""))
    except (ValueError, SignatureVerificationError):
        raise HTTPException(400, "Bad signature.")
    obj = event["data"]["object"]
    if event["type"] == "checkout.session.completed":
        billing.apply_session(obj)
    elif event["type"] == "customer.subscription.deleted":
        billing.apply_deleted_subscription(obj["id"])
    return {"received": True}
