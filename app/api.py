"""JSON API for the React front end (step 5.6: login, logout, roles, CSRF).
The research routes are open to visitors (SR33); only the administrator logs in.
The role is checked ON THE SERVER; the front end is never trusted (SR35, NFR8)."""
import re
import secrets
import time
from collections import defaultdict, deque
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from app import config, db, logs
from app.citations import best_citation       # shared with Edwin's citation checker: page and checker agree
from app.pipeline import answer, check_input

# The search index and the citation index, loaded by app/main.py when the site starts.
STATE = {"searcher": None, "index": None}

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
    """A logged-in, active account (since step 5.11 only administrators have one).
    401 = not logged in, 403 = account disabled."""
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
    before = db.account_for_log(body.email)       # the account's state BEFORE this try (for the log's reason)
    user, message = db.check_login(body.email, body.password)
    if not user:
        FAILED_BY_IP[ip].append(time.time())
        if before:                                 # a known account: the failure goes to its log (SPEC 11, 13 Nov)
            reason = before["reason"]
            if reason == "wrong password" and (db.account_for_log(body.email) or {}).get("reason") == "locked":
                reason = "wrong password (account now locked)"     # this try was the one that locked it
            if before["role"] == "user":
                logs.log_user(before["id"], "login_failed", {"reason": reason})
            else:                                  # an attempt ON an admin account, by anyone (SPEC 11)
                logs.log_admin(before["id"], before["email"], "login_failed",
                               detail={"reason": reason, "attempt_on_account": True})
        raise HTTPException(401, message)          # always "Wrong email or password."
    request.session.clear()                        # a new session at every login (no session fixation)
    request.session.update({"user_id": user["id"], "email": user["email"]})
    if user["role"] == "admin":
        logs.log_admin(user["id"], user["email"], "login")
    else:
        logs.log_user(user["id"], "login")
    return {"user": {"email": user["email"], "role": user["role"]}, "csrf": csrf_token(request)}


# ---------------- sign-up for visitors (SPEC 11, 2026-11-12) ----------------
# A visitor may make a 'user' account to keep their question history; nobody needs one to ask (SR33).
# At most SIGNUP_LIMIT_PER_IP new accounts per address in SIGNUP_LIMIT_MINUTES, in memory like the limits above.
SIGNUP_LIMIT_PER_IP, SIGNUP_LIMIT_MINUTES = 5, 60
SIGNUPS_BY_IP = defaultdict(deque)
MIN_PASSWORD = 10                    # the same as the Accounts page, until Joe's password policy replaces both


def valid_email(email):
    name, at, domain = email.strip().partition("@")
    return bool(name and at and "." in domain.strip(".") and " " not in email.strip() and len(email) <= 254)


@router.post("/signup")
def signup(request: Request, body: Login):
    ip = request.client.host if request.client else "unknown"
    window, made = SIGNUP_LIMIT_MINUTES * 60, SIGNUPS_BY_IP[ip]
    while made and made[0] < time.time() - window:
        made.popleft()
    if len(made) >= SIGNUP_LIMIT_PER_IP:
        raise HTTPException(429, "Too many new accounts from this address. Try again later.")
    if not valid_email(body.email):
        raise HTTPException(400, "Give a valid email address.")
    if len(body.password) < MIN_PASSWORD:
        raise HTTPException(400, f"Choose a password of at least {MIN_PASSWORD} characters.")
    user_id = db.create_visitor(body.email, body.password)       # never changes an existing account
    if user_id is None:
        raise HTTPException(409, "An account with this email already exists. Log in instead.")
    made.append(time.time())
    email = body.email.lower().strip()
    request.session.clear()                                      # logged in at once, in a new session
    request.session.update({"user_id": user_id, "email": email})
    logs.log_user(user_id, "signup")
    return {"user": {"email": email, "role": "user"}, "csrf": csrf_token(request)}


@router.post("/logout")
def logout(request: Request):
    uid, email = request.session.get("user_id"), request.session.get("email", "")
    role = db.active_role(uid) if uid else None
    if role == "admin":
        logs.log_admin(uid, email, "logout")
    elif role == "user":
        logs.log_user(uid, "logout")
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


# ---------------- question limit per IP address (step 5.12) ----------------
# The research page is open to visitors (SR33), so anyone could send questions in a loop and use up
# our model credit. One address may ask at most ASK_LIMIT_PER_IP questions in ASK_LIMIT_SECONDS.
# Same idea as the login limit above: kept in memory, one process, a restart empties it.
ASK_LIMIT_PER_IP, ASK_LIMIT_SECONDS = 10, 60
ASKED_BY_IP = defaultdict(deque)


def seconds_to_wait(ip):
    """0 if this address may ask now (and the question is counted), otherwise the seconds to wait."""
    now = time.time()
    asked = ASKED_BY_IP[ip]
    while asked and asked[0] <= now - ASK_LIMIT_SECONDS:      # forget questions older than the window
        asked.popleft()
    if len(asked) >= ASK_LIMIT_PER_IP:
        return int(asked[0] + ASK_LIMIT_SECONDS - now) + 1    # when the oldest one leaves the window
    asked.append(now)
    return 0


# ======================= RESEARCH (step 5.7) =======================
# Every question is answered on its own by pipeline.answer (Edwin): earlier questions are NOT used.
class Question(BaseModel):
    question: str


def decision_info(decision_ids):
    """Citation, docket number and CourtListener link of each decision, from OUR database (SR21)."""
    with db.connect() as con:
        rows = con.execute("SELECT decision_id, citations, docket_number, source_url FROM decisions "
                           "WHERE decision_id = ANY(%s)", (list(decision_ids),)).fetchall()
    return {r["decision_id"]: r for r in rows}


def citation_label(p, d):
    """How a passage is cited in the answer, e.g. "Loper Bright ..., No. 22-451 (2024) · Majority"
    (the same text as the old Jinja page)."""
    cite = best_citation(d["citations"]) if d and d["citations"] else f"No. {d['docket_number'] if d else '?'}"
    return f"{p['case_name']}, {cite} ({p['date_filed'][:4]}) · {p['opinion_label']}"


def public_answer(r):
    """What the user sees, built from the pipeline's result. Only sentences that passed the
    verifier (shown_sentences); none when the status is NOT_SUPPORTED or ERROR (SR28)."""
    passages = dict(r["passages"])
    info = decision_info({p["decision_id"] for p in passages.values()})
    return {
        "question": r["question"], "status": r["status"], "reason": r["reason"],
        "support_score": r["support_score"], "top_score": r["top_score"], "ms_total": r["ms_total"],
        "removed_count": len(r["removed"]),
        "sentences": [{"text": s["text"],
                       "citations": [{"pid": pid, "chunk_id": passages[pid]["chunk_id"], "quote": s.get("quote", ""),
                                      "label": citation_label(passages[pid], info.get(passages[pid]["decision_id"]))}
                                     for pid in s["sources"]]}
                      for s in r["shown_sentences"]],
        "passages": [{"pid": pid, "chunk_id": p["chunk_id"], "case_name": p["case_name"],
                      "year": p["date_filed"][:4], "opinion_label": p["opinion_label"], "section": p["section"],
                      "is_syllabus": p["is_syllabus"], "score": p["score"], "text": p["text"],
                      "label": citation_label(p, info.get(p["decision_id"]))}
                     for pid, p in r["passages"]],
    }


@router.post("/ask")
def ask(request: Request, body: Question):
    """Open to visitors, without an account (SR33, FR1). The CSRF check of the router still applies:
    the visitor's browser gets its token from GET /api/me with its own session."""
    error = check_input(body.question)                                         # SR3
    if error:
        raise HTTPException(400, error)
    wait = seconds_to_wait(request.client.host if request.client else "unknown")   # step 5.12
    if wait:                                    # refused BEFORE the model is called, and not saved
        uid = request.session.get("user_id")
        if uid and db.active_role(uid) == "user":                   # the refusal goes to the account's log
            logs.log_user(uid, "refused", {"reason": "questions per minute", "wait_seconds": wait})
        raise HTTPException(429, f"Too many questions from your address: at most {ASK_LIMIT_PER_IP} questions "
                                 f"per minute. Please wait {wait} seconds and try again.",
                            headers={"Retry-After": str(wait)})
    if STATE["searcher"] is None:
        raise HTTPException(503, "The search index is not ready yet.")
    r = answer(body.question, STATE["searcher"], STATE["index"], db.get_settings())
    shown = public_answer(r)
    asker = request.session.get("user_id")                      # a logged-in account keeps its history (SPEC 11)
    if asker and db.active_role(asker) is None:
        asker = None
    shown["id"] = db.log_query(r, user_id=asker, shown=shown)   # FR28, SR41 (no account: user_id stays empty)
    if asker and db.active_role(asker) == "user":
        logs.log_user(asker, "question", {"status": shown["status"]}, query_id=shown["id"])
    return shown


# ---------------- the question history of a logged-in account (SPEC 11, 2026-11-12) ----------------
@router.get("/history")
def history(user=Depends(require_user)):
    """Only the asking account's own questions, newest first. Not logged in: 401."""
    return [{**q, "created_at": q["created_at"].isoformat()} for q in db.user_history(user["id"])]


@router.get("/history/{query_id}")
def history_item(query_id: int, user=Depends(require_user)):
    """One of the account's own questions with the answer as it was shown; someone else's: 404."""
    q = db.user_question(user["id"], query_id)
    if not q:
        raise HTTPException(404, "Not found.")
    return {**q, "created_at": q["created_at"].isoformat()}


def passage_view(chunk_id, quote=""):
    """A passage inside its opinion: 2,500 characters before and after, and the quote marked
    (found even if spaces, line breaks or capitals differ). None if the passage does not exist."""
    with db.connect() as con:
        c = con.execute("""SELECT c.*, o.text AS opinion_text, o.label, d.case_name, d.date_filed,
                           d.citations, d.docket_number, d.source_url, d.licence
                           FROM chunks c JOIN opinions o USING (opinion_id)
                           JOIN decisions d ON d.decision_id = c.decision_id
                           WHERE c.chunk_id = %s""", (chunk_id,)).fetchone()
    if not c:
        return None
    text = c["opinion_text"]
    inside = text[c["start_char"]:c["end_char"]]
    pattern = r"\s+".join(re.escape(w) for w in quote.split())
    m = re.search(pattern, inside, re.IGNORECASE) if pattern else None
    return {"c": c, "before": text[max(0, c["start_char"] - 2500):c["start_char"]],
            "inside_before": inside[:m.start()] if m else inside, "marked": inside[m.start():m.end()] if m else "",
            "inside_after": inside[m.end():] if m else "", "after": text[c["end_char"]:c["end_char"] + 2500]}


@router.get("/passage/{chunk_id}")
def passage(chunk_id: str, quote: str = ""):
    """The side panel (SR31): the opinion around the passage, the quote highlighted, the CourtListener link.
    Open to visitors, like /api/ask (public opinions, public domain)."""
    v = passage_view(chunk_id, quote)
    if v is None:
        raise HTTPException(404, "Passage not found.")
    c = v.pop("c")
    return {"case_name": c["case_name"], "date_filed": str(c["date_filed"]), "opinion_label": c["label"],
            "section": c["section"], "citation": ", ".join(c["citations"] or []) or f"No. {c['docket_number']}",
            "source_url": c["source_url"], "licence": c["licence"], **v}
