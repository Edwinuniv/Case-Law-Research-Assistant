"""The site's own pages (Edwin, 2026-11-12): the contact form and the information the public pages need.
Public routes: GET /api/site, POST /api/contact (a visitor, no account, SR33; CSRF like every POST).
Admin routes: GET /api/admin/messages, POST /api/admin/messages/{message_id}/delete (admin role + CSRF, SR35).
Messages are kept with no deletion date (team decision, written on the privacy page); an administrator can
delete one. The visitor's IP address is used only in memory, to limit messages; it is never saved."""
import time
from collections import defaultdict, deque
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from app import api, config, db

router = APIRouter(prefix="/api", dependencies=[Depends(api.check_csrf)])
admin = APIRouter(prefix="/api/admin", dependencies=[Depends(api.check_csrf), Depends(api.require_admin)])

MAX_NAME, MAX_MESSAGE, MIN_MESSAGE = 100, 5000, 10
SENT_LIMIT, SENT_SECONDS = 3, 600            # at most 3 messages per address in 10 minutes (spam)
SENT_BY_IP = defaultdict(deque)              # memory only: never written to the database


@router.get("/site")
def site():
    """What the public pages need from the settings: the contact address (None when not set)."""
    return {"contact_email": config.CONTACT_EMAIL or None, "coverage": config.COVERAGE}


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
