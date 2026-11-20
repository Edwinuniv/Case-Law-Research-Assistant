"""My account (Edwin, SPEC 11, 2026-11-20, from CedarPay's profile, change password and delete account).
For a logged-in 'user' account only (administrators are managed by another administrator):
GET /api/account, POST /api/account/password, POST /api/account/delete. CSRF on every POST, like every /api route."""
import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from app import api, billing, db, emails, logs

router = APIRouter(prefix="/api/account", dependencies=[Depends(api.check_csrf)])


def user_account(user=Depends(api.require_user)):
    if user["role"] != "user":
        raise HTTPException(403, "Administrators have no account page: another administrator manages their account.")
    return user


def made_with_google(user_id):
    """An account made with "Sign in with Google" has a random password nobody knows (its sign-up row says so)."""
    with db.connect() as con:
        return bool(con.execute("SELECT 1 FROM user_log WHERE user_id = %s AND event = 'signup' "
                                "AND detail->>'method' = 'google'", (user_id,)).fetchone())


def email_of(user_id):
    with db.connect() as con:
        return con.execute("SELECT email FROM users WHERE id = %s", (user_id,)).fetchone()["email"]


@router.get("")
def account(user=Depends(user_account)):
    with db.connect() as con:
        row = con.execute("SELECT email, email_verified, created_at FROM users WHERE id = %s", (user["id"],)).fetchone()
    return {**row, "plan": api.plan_info(user["id"]), "google": made_with_google(user["id"])}


class NewPassword(BaseModel):
    current: str
    new: str


@router.post("/password")
def change_password(body: NewPassword, user=Depends(user_account)):
    if len(body.new) < api.MIN_PASSWORD:
        raise HTTPException(400, f"Choose a new password of at least {api.MIN_PASSWORD} characters.")
    email = email_of(user["id"])
    ok, _ = db.check_login(email, body.current)           # a wrong one counts as a failed login: 5 lock (SR36)
    if not ok:
        raise HTTPException(400, "Your current password is not right.")
    with db.connect() as con:
        con.execute("UPDATE users SET password_hash = %s WHERE id = %s",
                    (bcrypt.hashpw(body.new.encode(), bcrypt.gensalt()).decode(), user["id"]))
    logs.log_user(user["id"], "password_changed")
    emails.password_changed(email, "from your account page")
    return {"ok": True}


class Confirm(BaseModel):
    password: str | None = None
    email: str | None = None


@router.post("/delete")
def delete_account(request: Request, body: Confirm, user=Depends(user_account)):
    uid, email = user["id"], email_of(user["id"])
    google = made_with_google(uid)
    if google and body.email is not None:
        confirmed = body.email.strip().lower() == email
    else:
        confirmed = bool(body.password) and db.check_login(email, body.password)[0] is not None
    if not confirmed:
        raise HTTPException(400, "Type your email address to confirm." if google else "Type your password to confirm.")
    subscription = billing.subscription_of(uid)
    if subscription:                                      # a paid plan: the Stripe test subscription ends first
        billing.cancel_subscription(subscription)
    emails.account_deleted(email)                         # the address is still known: the last email
    with db.connect() as con:                             # one transaction: all of it, or nothing
        con.execute("DELETE FROM answer_feedback WHERE user_id = %s "
                    "OR query_id IN (SELECT id FROM query_log WHERE user_id = %s)", (uid, uid))
        con.execute("DELETE FROM query_log WHERE user_id = %s", (uid,))
        con.execute("DELETE FROM chats WHERE user_id = %s", (uid,))
        con.execute("DELETE FROM users WHERE id = %s", (uid,))   # its user log, codes and reset links go with it
    request.session.clear()
    return {"ok": True}
