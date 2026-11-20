"""My account: change password, delete account (SPEC 11, 2026-11-20, from CedarPay), written from the rule before the
code. Fake search and model from tests/test_api_research.py; no real email (mailer.send_later records). TEST database."""
import pytest
from tests.test_api_research import c as research_client, csrf, ask   # noqa: F401  (the fixture is used below)
from tests.test_visitor_accounts import sign_up, log_in, log_out, PW

READER = "reader@example.com"
NEW = "a-brand-new-password"


@pytest.fixture
def mail(monkeypatch):
    from app import mailer
    sent = []
    monkeypatch.setattr(mailer, "send_later", lambda to, subject, text, html=None, reply_to=None:
                        sent.append({"to": to, "subject": subject}))
    return sent


@pytest.fixture
def c(research_client, mail):
    from app import api
    api.SIGNUPS_BY_IP.clear()
    api.FAILED_BY_IP.clear()
    return research_client


def post(c, path, body):
    return c.post(path, json=body, headers=csrf(c))


def uid(clean_db, email=READER):
    with clean_db.connect() as con:
        row = con.execute("SELECT id FROM users WHERE email = %s", (email,)).fetchone()
    return row["id"] if row else None


def test_the_account_page_shows_the_account(c, clean_db):
    sign_up(c, READER)
    a = c.get("/api/account").json()
    assert a["email"] == READER and a["plan"]["plan"] == "free" and a["google"] is False and "created_at" in a


def test_only_a_logged_in_user_account_has_the_page(c, clean_db):
    assert c.get("/api/account").status_code == 401
    clean_db.create_user("boss@example.com", PW)
    log_in(c, "boss@example.com")
    assert c.get("/api/account").status_code == 403                  # administrators: another admin manages them


def test_changing_the_password_needs_the_current_one(c, clean_db, mail):
    sign_up(c, READER)
    assert post(c, "/api/account/password", {"current": "not-my-password", "new": NEW}).status_code == 400
    assert post(c, "/api/account/password", {"current": PW, "new": "short"}).status_code == 400
    assert post(c, "/api/account/password", {"current": PW, "new": NEW}).status_code == 200
    log_out(c)
    assert log_in(c, READER, PW).status_code == 401 and log_in(c, READER, NEW).status_code == 200
    assert "password" in mail[-1]["subject"].lower() and mail[-1]["to"] == READER
    with clean_db.connect() as con:
        events = [r["event"] for r in con.execute("SELECT event FROM user_log ORDER BY id")]
    assert "password_changed" in events


def test_five_wrong_current_passwords_lock_the_account(c, clean_db):
    sign_up(c, READER)
    for _ in range(5):
        post(c, "/api/account/password", {"current": "not-my-password", "new": NEW})
    log_out(c)
    assert log_in(c, READER, PW).status_code == 401                  # locked, like five failed logins (SR36)


def test_deleting_the_account_removes_everything_and_ends_the_session(c, clean_db, mail):
    sign_up(c, READER)
    user = uid(clean_db)
    qid = ask(c).json()["id"]
    post(c, "/api/feedback", {"query_id": qid, "helpful": True})
    assert post(c, "/api/account/delete", {"password": "wrong-password-1"}).status_code == 400
    assert post(c, "/api/account/delete", {"password": PW}).status_code == 200
    assert c.get("/api/me").json()["user"] is None and uid(clean_db) is None
    with clean_db.connect() as con:
        for table in ("query_log", "chats", "user_log", "answer_feedback"):
            assert con.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"] == 0, table
    assert mail[-1]["to"] == READER and "deleted" in mail[-1]["subject"].lower()
    assert log_in(c, READER, PW).status_code == 401


def test_a_google_account_confirms_with_its_email(c, clean_db, monkeypatch):
    from app import google_auth
    monkeypatch.setattr(google_auth, "CLIENT_ID", "client.apps.googleusercontent.com")
    monkeypatch.setattr(google_auth, "verify_credential", lambda credential: "g.reader@example.com")
    post(c, "/api/auth/google", {"credential": "x"})
    assert c.get("/api/account").json()["google"] is True
    assert post(c, "/api/account/delete", {"email": "someone@example.com"}).status_code == 400
    assert post(c, "/api/account/delete", {"email": "G.Reader@example.com "}).status_code == 200
    assert uid(clean_db, "g.reader@example.com") is None


def test_a_password_account_cannot_confirm_with_its_email_only(c, clean_db):
    sign_up(c, READER)
    assert post(c, "/api/account/delete", {"email": READER}).status_code == 400 and uid(clean_db)


def test_a_paid_subscription_is_cancelled_before_the_account_is_deleted(c, clean_db, monkeypatch):
    from app import billing
    cancelled = []
    monkeypatch.setattr(billing, "cancel_subscription", lambda sub: cancelled.append(sub))
    sign_up(c, READER)
    billing.switch(uid(clean_db), "paid", "cus_1", "sub_1")
    assert post(c, "/api/account/delete", {"password": PW}).status_code == 200
    assert cancelled == ["sub_1"]


def test_deleting_clears_the_session_cookie(c, clean_db):
    """A planted bug got through (2026-11-20): with the session kept, /api/me still showed nobody, because the account
    was gone. So the test reads the signed cookie itself (Starlette's format: base64 JSON, signed)."""
    import base64
    import json
    from itsdangerous import TimestampSigner
    from app import config
    sign_up(c, READER)
    post(c, "/api/account/delete", {"password": PW})
    cookie = c.cookies.get("session")
    data = json.loads(base64.b64decode(TimestampSigner(config.SESSION_SECRET).unsign(cookie))) if cookie else {}
    assert "user_id" not in data
