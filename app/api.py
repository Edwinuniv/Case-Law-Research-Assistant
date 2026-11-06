"""JSON API for the React front end (step 5.6: login, logout, roles, CSRF).
Every route checks the role ON THE SERVER; the front end is never trusted (SR35, NFR8)."""
import secrets
import time
from collections import defaultdict, deque
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from app import config, db

# ---------------- CSRF (step 5.6) ----------------
# The server keeps a random token in the session (a cookie that JavaScript cannot read).
# GET /api/me gives it to React, and React sends it back in the X-CSRF-Token header with every POST.
# Another website can make the browser send our cookie, but it cannot read the token, so its POST fails.
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def csrf_token(request):
    if "csrf" not in request.session:
        request.session["csrf"] = secrets.token_urlsafe(32)
    return request.session["csrf"]


def check_csrf(request: Request):
    if request.method in SAFE_METHODS:
        return
    expected = request.session.get("csrf", "")
    sent = request.headers.get("X-CSRF-Token", "")
    if not expected or not secrets.compare_digest(sent, expected):
        raise HTTPException(403, "Missing or wrong CSRF token. Reload the page.")


router = APIRouter(prefix="/api", dependencies=[Depends(check_csrf)])   # applies to EVERY /api route


# ---------------- who is logged in, and with which role ----------------
def require_user(request: Request):
    """Any logged-in account ('user' or 'admin'). 401 = not logged in, 403 = account disabled."""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(401, "Please log in.")
    role = db.active_role(user_id)              # read from the database at EVERY request
    if role is None:
        request.session.clear()
        raise HTTPException(403, "This account is disabled.")
    return {"id": user_id, "email": request.session.get("email"), "role": role}


def require_admin(user=Depends(require_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Administrators only.")
    return user


# ---------------- login rate limit per IP address (step 5.6) ----------------
# On top of the lock of one account (SR36, in db.py): one address may fail at most
# LOGIN_LIMIT_PER_IP times in LOGIN_LIMIT_MINUTES, whatever emails it tries.
# Kept in memory: the site runs as one process; a restart empties it.
# (Set here, not in config.py, because config.py is Yasser's file.)
LOGIN_LIMIT_PER_IP, LOGIN_LIMIT_MINUTES = 10, 15
FAILED_BY_IP = defaultdict(deque)


def too_many_failures(ip):
    window = LOGIN_LIMIT_MINUTES * 60
    failures = FAILED_BY_IP[ip]
    while failures and failures[0] < time.time() - window:     # forget failures older than the window
        failures.popleft()
    return len(failures) >= LOGIN_LIMIT_PER_IP


class Login(BaseModel):
    email: str
    password: str


@router.post("/login")
def login(request: Request, body: Login):
    ip = request.client.host if request.client else "unknown"
    if too_many_failures(ip):
        raise HTTPException(429, "Too many failed logins from this address. Try again later.")
    user, message = db.check_login(body.email, body.password)
    if not user:
        FAILED_BY_IP[ip].append(time.time())
        raise HTTPException(401, message)          # always "Wrong email or password."
    request.session.clear()                        # a new session at every login (no session fixation)
    request.session.update({"user_id": user["id"], "email": user["email"]})
    return {"user": {"email": user["email"], "role": user["role"]}, "csrf": csrf_token(request)}


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    """Who is logged in (or null), the CSRF token, and what the corpus covers (SR30)."""
    user = None
    if request.session.get("user_id"):
        role = db.active_role(request.session["user_id"])
        if role:
            user = {"email": request.session.get("email"), "role": role}
        else:
            request.session.clear()
    return {"user": user, "csrf": csrf_token(request), "coverage": config.COVERAGE,
            "examples": config.EXAMPLE_QUESTIONS}
