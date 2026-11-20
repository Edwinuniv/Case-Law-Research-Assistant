"""The verification code (SPEC 11, 2026-11-20, rule 2), written from the rule before the code.
Fake search and model from tests/test_api_research.py; no real email (mailer.send_later records). TEST database."""
import re
import pytest
from tests.test_api_research import c as research_client, csrf, ask   # noqa: F401  (the fixture is used below)
from tests.test_visitor_accounts import sign_up, log_in, log_out, PW

READER = "reader@example.com"


@pytest.fixture
def mail(monkeypatch):
    from app import config, mailer
    monkeypatch.setattr(config, "EMAIL_VERIFICATION", True)        # the tests of this rule switch it on
    sent = []
    monkeypatch.setattr(mailer, "send_later", lambda to, subject, text, html=None, reply_to=None:
                        sent.append({"to": to, "subject": subject, "text": text, "html": html, "reply_to": reply_to}))
    return sent


@pytest.fixture
def c(research_client, mail):
    from app import api
    api.SIGNUPS_BY_IP.clear()
    return research_client


def code_in(message):
    return re.search(r"\b(\d{6})\b", message["text"]).group(1)


def verify(c, code):
    return c.post("/api/verify/check", json={"code": code}, headers=csrf(c))


def resend(c):
    return c.post("/api/verify/send", headers=csrf(c))


def verified(c):
    return c.get("/api/me").json()["email_verified"]


def test_sign_up_sends_a_six_digit_code_and_stores_only_a_fingerprint(c, mail, clean_db):
    sign_up(c, READER)
    assert [m["to"] for m in mail] == [READER] and verified(c) is False
    code = code_in(mail[0])
    with clean_db.connect() as con:
        rows = con.execute("SELECT * FROM email_codes").fetchall()
    assert len(rows) == 1 and code not in str(rows)


def test_the_right_code_verifies_the_account_and_sends_a_welcome(c, mail, clean_db):
    sign_up(c, READER)
    r = verify(c, code_in(mail[0]))
    assert r.status_code == 200 and verified(c) is True
    assert mail[-1]["to"] == READER and "welcome" in mail[-1]["subject"].lower()
    with clean_db.connect() as con:
        events = [r["event"] for r in con.execute("SELECT event FROM user_log ORDER BY id")]
    assert "email_verified" in events


def test_five_wrong_tries_then_even_the_right_code_is_refused(c, mail):
    sign_up(c, READER)
    code = code_in(mail[0])
    wrong = "000000" if code != "000000" else "111111"
    for left in (4, 3, 2, 1, 0):
        r = verify(c, wrong)
        words = f"{left} {'try' if left == 1 else 'tries'} left"
        assert r.status_code == 400 and (words in r.json()["detail"] or left == 0)
    r = verify(c, code)
    assert r.status_code == 400 and "new code" in r.json()["detail"] and verified(c) is False


def test_an_expired_code_is_refused(c, mail, clean_db):
    sign_up(c, READER)
    with clean_db.connect() as con:
        con.execute("UPDATE email_codes SET expires_at = now() - interval '1 minute'")
    r = verify(c, code_in(mail[0]))
    assert r.status_code == 400 and "expired" in r.json()["detail"] and verified(c) is False


def test_a_new_code_at_most_once_a_minute_and_it_replaces_the_old_one(c, mail, clean_db):
    sign_up(c, READER)
    old = code_in(mail[0])
    assert resend(c).status_code == 429 and len(mail) == 1          # too soon
    with clean_db.connect() as con:
        con.execute("UPDATE email_codes SET sent_at = now() - interval '2 minutes'")
    assert resend(c).status_code == 200 and len(mail) == 2
    new = code_in(mail[1])
    if new != old:
        assert verify(c, old).status_code == 400                    # the old code no longer works
    assert verify(c, new).status_code == 200


def test_the_code_routes_need_a_logged_in_unverified_account(c, mail):
    assert resend(c).status_code == 401 and verify(c, "123456").status_code == 401
    sign_up(c, READER)
    verify(c, code_in(mail[0]))
    assert resend(c).status_code == 400                             # already verified: nothing to send


def test_an_unverified_account_asks_one_question_then_must_verify(c, mail):
    sign_up(c, READER)
    assert ask(c).status_code == 200
    r = ask(c, "And what about unofficial acts?")
    assert r.status_code == 403 and "verify" in r.json()["detail"].lower()
    verify(c, code_in(mail[0]))
    assert ask(c, "And what about unofficial acts?").status_code == 200


def test_an_unverified_account_cannot_buy_the_paid_plan(c, mail, monkeypatch):
    from app import billing
    monkeypatch.setattr(billing, "SECRET_KEY", "sk_test_123")
    monkeypatch.setattr(billing, "PRICE_ID", "price_123")
    monkeypatch.setattr(billing, "create_checkout", lambda uid, email, base: "https://checkout.stripe.test/s")
    sign_up(c, READER)
    r = c.post("/api/billing/checkout", headers=csrf(c))
    assert r.status_code == 403 and "verify" in r.json()["detail"].lower()
    verify(c, code_in(mail[0]))
    assert c.post("/api/billing/checkout", headers=csrf(c)).status_code == 200


def test_google_and_administrator_accounts_are_verified_without_a_code(c, mail, clean_db, monkeypatch):
    from app import google_auth
    monkeypatch.setattr(google_auth, "CLIENT_ID", "client.apps.googleusercontent.com")
    monkeypatch.setattr(google_auth, "verify_credential", lambda credential: "g.reader@example.com")
    assert c.post("/api/auth/google", json={"credential": "x"}, headers=csrf(c)).status_code == 200
    assert verified(c) is True and mail == []                       # Google checked the address
    log_out(c)
    clean_db.create_user("boss@example.com", PW)
    log_in(c, "boss@example.com")
    assert verified(c) is True and mail == []


def test_google_sign_in_verifies_an_account_made_with_a_password(c, mail, monkeypatch):
    from app import google_auth
    sign_up(c, READER)
    log_out(c)
    monkeypatch.setattr(google_auth, "CLIENT_ID", "client.apps.googleusercontent.com")
    monkeypatch.setattr(google_auth, "verify_credential", lambda credential: READER)
    c.post("/api/auth/google", json={"credential": "x"}, headers=csrf(c))
    assert verified(c) is True


def test_accounts_made_before_the_rule_are_verified_new_ones_are_not(clean_db):
    clean_db.create_visitor("old@example.com", PW)
    with clean_db.connect() as con:
        con.execute("ALTER TABLE users DROP COLUMN email_verified")   # as on a database from before the rule
    clean_db.init_db()                                                # the migration at the next start
    clean_db.create_visitor("new@example.com", PW)
    with clean_db.connect() as con:
        rows = {r["email"]: r["email_verified"] for r in con.execute("SELECT email, email_verified FROM users")}
    assert rows == {"old@example.com": True, "new@example.com": False}


def test_with_verification_off_no_code_is_sent_and_nothing_is_limited(c, mail, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "EMAIL_VERIFICATION", False)
    sign_up(c, READER)
    assert mail == []
    assert ask(c).status_code == 200 and ask(c, "And what about unofficial acts?").status_code == 200


def test_the_site_still_starts_after_an_account_is_verified(clean_db):
    """Seen on 2026-11-20 on a copy of the real database: the migrations re-made the log's list of events twice,
    the older list without email_verified, so once an account was verified the next start failed."""
    from app import logs
    uid = clean_db.create_visitor("reader@example.com", PW)
    logs.log_user(uid, "email_verified")
    clean_db.init_db()                                                # the next start of the site
    clean_db.init_db()


def test_at_most_five_codes_a_day_the_sign_up_code_included(c, mail, clean_db):
    """Yasser's review (2026-11-20): with only "one a minute", 5 tries x 1,440 codes = 7,200 guesses a day."""
    def a_minute_later():
        with clean_db.connect() as con:
            con.execute("UPDATE email_codes SET sent_at = now() - interval '2 minutes'")
    sign_up(c, READER)                                              # code 1 of the day
    for _ in range(4):                                              # codes 2 to 5
        a_minute_later()
        assert resend(c).status_code == 200
    a_minute_later()
    r = resend(c)                                                   # code 6: refused, nothing sent
    assert r.status_code == 429 and "tomorrow" in r.json()["detail"] and len(mail) == 5
    with clean_db.connect() as con:                                 # 24 hours later the count starts again
        con.execute("UPDATE email_codes SET window_start = now() - interval '25 hours', "
                    "sent_at = now() - interval '25 hours'")
    assert resend(c).status_code == 200 and len(mail) == 6
