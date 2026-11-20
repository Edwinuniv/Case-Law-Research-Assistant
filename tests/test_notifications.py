"""Notifications and the contact form by email (SPEC 11, 2026-11-20, rules 3 and 4), written from the rule before
the code. No real email: mailer.send_later records every message. TEST database."""
import pytest
from fastapi.testclient import TestClient
from tests.test_api_research import c as research_client, csrf   # noqa: F401  (the fixture is used below)
from tests.test_visitor_accounts import sign_up, log_in, PW

READER = "reader@example.com"


@pytest.fixture
def mail(monkeypatch):
    from app import mailer
    sent = []
    monkeypatch.setattr(mailer, "send_later", lambda to, subject, text, html=None, reply_to=None:
                        sent.append({"to": to, "subject": subject, "text": text, "html": html, "reply_to": reply_to}))
    return sent


@pytest.fixture
def c(research_client, mail):
    from app import api, api_site
    api.SIGNUPS_BY_IP.clear()
    api_site.SENT_BY_IP.clear()
    api_site.RESETS_BY_IP.clear()
    return research_client


@pytest.fixture
def admin(c, clean_db):
    """Another browser, logged in as an administrator."""
    from app import main
    clean_db.create_user("boss@example.com", PW)
    with TestClient(main.app, client=("203.0.113.9", 50000)) as a:
        log_in(a, "boss@example.com")
        yield a


def user_id(clean_db, email=READER):
    with clean_db.connect() as con:
        return con.execute("SELECT id FROM users WHERE email = %s", (email,)).fetchone()["id"]


def to_reader(mail):
    return [m for m in mail if m["to"] == READER]


def test_a_password_reset_sends_a_password_changed_notice(c, mail, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "PUBLIC_URL", "https://verdicta.example")
    sign_up(c, READER)
    c.post("/api/password/forgot", json={"email": READER}, headers=csrf(c))
    link = next(m for m in mail if "reset" in m["subject"].lower())
    token = link["text"].split("/reset?token=")[1].split()[0]
    assert c.post("/api/password/reset", json={"token": token, "password": "a-brand-new-password"},
                  headers=csrf(c)).status_code == 200
    assert "password" in to_reader(mail)[-1]["subject"].lower() and "changed" in to_reader(mail)[-1]["subject"].lower()


def test_an_administrator_changing_the_plan_notifies_the_account(c, admin, mail, clean_db):
    sign_up(c, READER)
    uid = user_id(clean_db)
    admin.post(f"/api/admin/users/{uid}/plan", json={"plan": "paid"}, headers=csrf(admin))
    last = to_reader(mail)[-1]
    assert "paid" in last["subject"].lower() and "100" in last["text"]   # the new daily limit
    admin.post(f"/api/admin/users/{uid}/plan", json={"plan": "free"}, headers=csrf(admin))
    assert "free" in to_reader(mail)[-1]["subject"].lower()


def test_stripe_changing_the_plan_notifies_the_account_once(c, mail, clean_db):
    from app import billing
    sign_up(c, READER)
    uid = user_id(clean_db)
    before = len(to_reader(mail))
    billing.switch(uid, "paid", "cus_1", "sub_1")
    billing.switch(uid, "paid", "cus_1", "sub_1")                    # the same event twice: one email
    assert len(to_reader(mail)) == before + 1 and "paid" in to_reader(mail)[-1]["subject"].lower()


def test_disabling_and_enabling_an_account_notifies_it(c, admin, mail, clean_db):
    sign_up(c, READER)
    uid = user_id(clean_db)
    admin.post(f"/api/admin/users/{uid}/toggle", headers=csrf(admin))
    assert "disabled" in to_reader(mail)[-1]["subject"].lower()
    admin.post(f"/api/admin/users/{uid}/toggle", headers=csrf(admin))
    assert "enabled" in to_reader(mail)[-1]["subject"].lower()


def test_a_contact_message_goes_to_the_team_with_reply_to_the_visitor(c, mail, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "CONTACT_EMAIL", "edwin@example.com, joe@example.com")
    body = {"name": "A <b>Visitor</b>", "email": "visitor@example.com",
            "message": "Your site helped me <script>x</script> find Bostock."}
    assert c.post("/api/contact", json=body, headers=csrf(c)).status_code == 200
    assert sorted(m["to"] for m in mail) == ["edwin@example.com", "joe@example.com", "verdicta.team@gmail.com"]
    assert all(m["reply_to"] == "visitor@example.com" for m in mail)
    assert "<script>" not in mail[0]["html"] and "&lt;script&gt;" in mail[0]["html"]
    assert "find Bostock" in mail[0]["text"]
    assert all(m["to"] != "visitor@example.com" for m in mail)       # no automatic email to the visitor


def test_no_email_carries_the_text_of_a_question(c, mail, clean_db):
    from tests.test_api_research import ask
    sign_up(c, READER)
    ask(c, "Is the President immune from prosecution for secret things?")
    assert not any("secret things" in m["text"] for m in mail)
