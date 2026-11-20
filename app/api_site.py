"""The site's own pages (Edwin, 2026-11-12): the contact form and the information the public pages need.
Public routes: GET /api/site, POST /api/contact (a visitor, no account, SR33; CSRF like every POST).
Admin routes: GET /api/admin/messages, POST /api/admin/messages/{message_id}/delete (admin role + CSRF, SR35).
Forgot password (SPEC 11, 2026-11-19): POST /api/password/forgot and /api/password/reset (visitors, CSRF).
Emails (SPEC 11, 2026-11-20): POST /api/verify/send and /api/verify/check (the logged-in account's code); a contact
message is also emailed to the team (CONTACT_EMAIL + TEAM_EMAIL).
Messages are kept with no deletion date (team decision, written on the privacy page); an administrator can
delete one. The visitor's IP address is used only in memory, to limit messages; it is never saved."""
import time
from collections import defaultdict, deque
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel
from app import api, config, db, emails, logs, resets, verification

router = APIRouter(prefix="/api", dependencies=[Depends(api.check_csrf)])
admin = APIRouter(prefix="/api/admin", dependencies=[Depends(api.check_csrf), Depends(api.require_admin)])

MAX_NAME, MAX_MESSAGE, MIN_MESSAGE = 100, 5000, 10
SENT_LIMIT, SENT_SECONDS = 3, 600            # at most 3 messages per address in 10 minutes (spam)
SENT_BY_IP = defaultdict(deque)              # memory only: never written to the database


@router.get("/site")
def site():
    """What the public pages need from the settings: the contact addresses (CONTACT_EMAIL, separated by commas;
    an empty list when not set) and the coverage line."""
    return {"contact_emails": [e.strip() for e in config.CONTACT_EMAIL.split(",") if e.strip()], "coverage": config.COVERAGE}


class Message(BaseModel):
    name: str
    email: str
    message: str


def seconds_to_wait(ip):
    now, sent = time.monotonic(), SENT_BY_IP[ip]
    while sent and now - sent[0] > SENT_SECONDS:
        sent.popleft()
    return int(SENT_SECONDS - (now - sent[0])) + 1 if len(sent) >= SENT_LIMIT else 0


@router.post("/contact")
def contact(request: Request, body: Message):
    name, email, message = body.name.strip(), body.email.strip(), body.message.strip()
    if not name or len(name) > MAX_NAME:
        raise HTTPException(400, f"Please give your name ({MAX_NAME} characters at most).")
    if "@" not in email or "." not in email.split("@")[-1] or len(email) > 200 or " " in email:
        raise HTTPException(400, "Please give an email address we can answer.")
    if not MIN_MESSAGE <= len(message) <= MAX_MESSAGE:
        raise HTTPException(400, f"Please write a message of {MIN_MESSAGE} to {MAX_MESSAGE:,} characters.")
    ip = request.client.host if request.client else "unknown"
    wait = seconds_to_wait(ip)
    if wait:
        raise HTTPException(429, f"Too many messages from your address. Please try again in {wait // 60 + 1} minutes.")
    SENT_BY_IP[ip].append(time.monotonic())
    with db.connect() as con:
        con.execute("INSERT INTO contact_messages (name, email, message) VALUES (%s, %s, %s)", (name, email, message))
    emails.contact_to_team(team_addresses(), name, email, message)     # Reply-To the visitor; nothing to the visitor
    return {"ok": True}


def team_addresses():
    """The contact page's addresses and the team's Gmail account, each once."""
    found = [e.strip() for e in config.CONTACT_EMAIL.split(",") if e.strip()] + [config.TEAM_EMAIL]
    return list(dict.fromkeys(a.lower() for a in found))



# ---------------- forgot password (SPEC 11, 2026-11-19) ----------------
RESET_LIMIT, RESET_SECONDS = 5, 900          # at most 5 asks per address in 15 minutes
RESETS_BY_IP = defaultdict(deque)            # memory only, like SENT_BY_IP
FORGOT_ANSWER = ("If an account exists for this email, we have sent a link to reset its password. "
                 "It works once, for 30 minutes. Check your spam folder too.")
BAD_LINK = "This link is not valid any more. Ask for a new one."


class Forgot(BaseModel):
    email: str


class Reset(BaseModel):
    token: str
    password: str


def email_reset_link(email):
    """Runs after the answer is sent, so the answer takes the same time for every email."""
    token = resets.new_token(email)
    if token:                                         # the link is built on PUBLIC_URL, never the request's Host
        emails.reset_link(email.lower().strip(), f"/reset?token={token}", resets.TOKEN_MINUTES)


@router.post("/password/forgot")
def password_forgot(request: Request, body: Forgot, background: BackgroundTasks):
    ip = request.client.host if request.client else "unknown"
    now, asked = time.monotonic(), RESETS_BY_IP[ip]
    while asked and now - asked[0] > RESET_SECONDS:
        asked.popleft()
    if len(asked) >= RESET_LIMIT:
        raise HTTPException(429, "Too many requests from your address. Please try again later.")
    asked.append(now)
    background.add_task(email_reset_link, body.email[:254])
    return {"message": FORGOT_ANSWER}                 # the same answer for every email


@router.post("/password/reset")
def password_reset(body: Reset):
    if len(body.password) < api.MIN_PASSWORD:         # checked first: a short password does not use the link
        raise HTTPException(400, f"Choose a password of at least {api.MIN_PASSWORD} characters.")
    user_id = resets.use_token(body.token, body.password)
    if not user_id:
        raise HTTPException(400, BAD_LINK)            # wrong, used or expired: one message
    logs.log_user(user_id, "password_reset")
    emails.password_changed(account_email(user_id))   # a security notice (SPEC 11, 2026-11-20)
    return {"ok": True}


def account_email(user_id):
    with db.connect() as con:
        return con.execute("SELECT email FROM users WHERE id = %s", (user_id,)).fetchone()["email"]


# ---------------- email verification (SPEC 11, 2026-11-20) ----------------
class Code(BaseModel):
    code: str


@router.post("/verify/send")
def verify_send(user=Depends(api.require_user)):
    if db.email_verified(user["id"]):
        raise HTTPException(400, "Your email is already verified.")
    sent = verification.send_code(user["id"], account_email(user["id"]))
    if sent == "wait":
        raise HTTPException(429, "Wait a minute before asking for a new code.")
    if sent == "daily":                               # at most 5 codes in 24 hours (Yasser's review)
        raise HTTPException(429, "You have asked for 5 codes today. Try again tomorrow, or write to us from the contact page.")
    return {"ok": True}


CODE_REFUSED = {"missing": "Ask for a new code first.", "expired": "This code has expired. Ask for a new code.",
                "tries": "Too many wrong tries. Ask for a new code."}


@router.post("/verify/check")
def verify_check(body: Code, user=Depends(api.require_user)):
    result = verification.check(user["id"], body.code[:20])
    if result.startswith("wrong:"):
        left = int(result.split(":")[1])
        raise HTTPException(400, f"This code is not right. {left} {'try' if left == 1 else 'tries'} left.")
    if result != "ok":
        raise HTTPException(400, CODE_REFUSED[result])
    logs.log_user(user["id"], "email_verified")
    emails.welcome(account_email(user["id"]))
    return {"ok": True}


def messages():
    with db.connect() as con:
        return con.execute("SELECT id, created_at, name, email, message FROM contact_messages ORDER BY id DESC").fetchall()


@admin.get("/messages")
def admin_messages():
    return messages()


@admin.post("/messages/{message_id}/delete")
def admin_delete(message_id: int):
    with db.connect() as con:
        if not con.execute("DELETE FROM contact_messages WHERE id = %s RETURNING id", (message_id,)).fetchone():
            raise HTTPException(404, "No such message.")
    return messages()
