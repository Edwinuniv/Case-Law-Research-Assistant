"""In-app notifications (SPEC 11, 2026-11-20, from CedarPay), written from the rule before the code. No real email.
Fake search and model from tests/test_api_research.py; TEST database."""
import pytest
from fastapi.testclient import TestClient
from tests.test_api_research import c as research_client, csrf   # noqa: F401  (the fixture is used below)
from tests.test_visitor_accounts import sign_up, log_in, PW

READER = "reader@example.com"


@pytest.fixture
def c(research_client, monkeypatch):
    from app import api, mailer
    api.SIGNUPS_BY_IP.clear()
    monkeypatch.setattr(mailer, "send_later", lambda *a, **k: None)
    return research_client


@pytest.fixture
def admin(c, clean_db):
    from app import main
    clean_db.create_user("boss@example.com", PW)
    with TestClient(main.app, client=("203.0.113.9", 50000)) as a:
        log_in(a, "boss@example.com")
        yield a


def uid(clean_db, email=READER):
    return clean_db.connect().execute("SELECT id FROM users WHERE email = %s", (email,)).fetchone()["id"]


def notices(c):
    return c.get("/api/notifications").json()


def test_a_plan_change_and_a_password_change_become_notices(c, admin, clean_db):
    sign_up(c, READER)
    admin.post(f"/api/admin/users/{uid(clean_db)}/plan", json={"plan": "paid"}, headers=csrf(admin))
    c.post("/api/account/password", json={"current": PW, "new": "a-brand-new-password"}, headers=csrf(c))
    n = notices(c)
    assert n["unread"] == 2
    assert [x["kind"] for x in n["items"]] == ["password_changed", "plan_changed"]   # newest first
    assert "Paid" in n["items"][1]["text"] and n["items"][1]["link"] == "/pricing"


def test_the_welcome_after_verifying(c, clean_db, monkeypatch):
    from app import config, verification
    monkeypatch.setattr(config, "EMAIL_VERIFICATION", True)
    codes = []
    monkeypatch.setattr(verification.emails, "verification_code", lambda to, code, minutes: codes.append(code))
    sign_up(c, READER)
    c.post("/api/verify/check", json={"code": codes[0]}, headers=csrf(c))
    assert [x["kind"] for x in notices(c)["items"]] == ["welcome"]


def test_disabling_and_enabling_are_notices_read_at_the_next_login(c, admin, clean_db):
    sign_up(c, READER)
    user = uid(clean_db)
    admin.post(f"/api/admin/users/{user}/toggle", headers=csrf(admin))
    admin.post(f"/api/admin/users/{user}/toggle", headers=csrf(admin))
    log_in(c, READER)
    assert [x["kind"] for x in notices(c)["items"]] == ["account_enabled", "account_disabled"]


def test_opening_marks_them_read(c, admin, clean_db):
    sign_up(c, READER)
    admin.post(f"/api/admin/users/{uid(clean_db)}/plan", json={"plan": "paid"}, headers=csrf(admin))
    assert c.post("/api/notifications/read", headers=csrf(c)).status_code == 200
    n = notices(c)
    assert n["unread"] == 0 and len(n["items"]) == 1 and n["items"][0]["read"] is True


def test_only_ones_own_notices_and_none_for_a_visitor(c, admin, clean_db):
    from app import main
    sign_up(c, READER)
    admin.post(f"/api/admin/users/{uid(clean_db)}/plan", json={"plan": "paid"}, headers=csrf(admin))
    with TestClient(main.app, client=("203.0.113.7", 50001)) as other:
        assert other.get("/api/notifications").status_code == 401
        sign_up(other, "someone@example.com")
        assert notices(other) == {"unread": 0, "items": []}


def test_at_most_50_kept_and_20_shown(c, clean_db):
    from app import notices as n
    sign_up(c, READER)
    for i in range(60):
        n.add(uid(clean_db), "plan_changed", f"notice {i}")
    with clean_db.connect() as con:
        assert con.execute("SELECT count(*) AS n FROM notifications").fetchone()["n"] == 50
    got = notices(c)
    assert len(got["items"]) == 20 and got["items"][0]["text"] == "notice 59" and got["unread"] == 50
