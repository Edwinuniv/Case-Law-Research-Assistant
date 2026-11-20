"""Announcements (SPEC 11, 2026-11-20, from CedarPay), written from the rule before the code. TEST database."""
import pytest
from fastapi.testclient import TestClient
from tests.test_api_research import c as research_client, csrf   # noqa: F401  (the fixture is used below)
from tests.test_visitor_accounts import sign_up, log_in, PW


@pytest.fixture
def c(research_client):
    from app import api
    api.SIGNUPS_BY_IP.clear()
    return research_client


@pytest.fixture
def admin(c, clean_db):
    from app import main
    clean_db.create_user("boss@example.com", PW)
    with TestClient(main.app, client=("203.0.113.9", 50000)) as a:
        log_in(a, "boss@example.com")
        yield a


def post(client, body):
    return client.post("/api/admin/announcements", json=body, headers=csrf(client))


def shown(c):
    return [a["text"] for a in c.get("/api/announcements").json()]


def test_an_active_announcement_is_shown_to_everyone(c, admin):
    assert post(admin, {"text": "Maintenance tonight at 22:00.", "level": "warning", "days": 1}).status_code == 200
    assert shown(c) == ["Maintenance tonight at 22:00."]
    assert c.get("/api/announcements").json()[0]["level"] == "warning"


def test_ended_and_coming_announcements_are_not_shown(c, admin, clean_db):
    post(admin, {"text": "Coming", "level": "info", "days": 2, "starts_in_hours": 5})
    post(admin, {"text": "Ended", "level": "info", "days": 1})
    with clean_db.connect() as con:
        con.execute("UPDATE announcements SET ends_at = now() - interval '1 minute' WHERE text = 'Ended'")
    assert shown(c) == []
    listed = {a["text"]: a["state"] for a in admin.get("/api/admin/announcements").json()}
    assert listed == {"Coming": "coming", "Ended": "ended"}


def test_at_most_three_newest_first(c, admin):
    for i in range(4):
        post(admin, {"text": f"Message {i}", "level": "info", "days": 1})
    assert shown(c) == ["Message 3", "Message 2", "Message 1"]


@pytest.mark.parametrize("body", [{"text": "", "level": "info", "days": 1}, {"text": "x" * 301, "level": "info", "days": 1},
                                  {"text": "Hi", "level": "danger", "days": 1}, {"text": "Hi", "level": "info", "days": 31},
                                  {"text": "Hi", "level": "info", "days": 0}])
def test_bad_announcements_are_refused(c, admin, body):
    assert post(admin, body).status_code == 400 and shown(c) == []


def test_only_administrators_write_them(c, clean_db):
    assert post(c, {"text": "Hi", "level": "info", "days": 1}).status_code == 401
    sign_up(c, "reader@example.com")
    assert post(c, {"text": "Hi", "level": "info", "days": 1}).status_code == 403


def test_deleting_removes_it_and_both_are_in_the_admin_log(c, admin, clean_db):
    post(admin, {"text": "Soon gone", "level": "info", "days": 1})
    aid = admin.get("/api/admin/announcements").json()[0]["id"]
    assert admin.post(f"/api/admin/announcements/{aid}/delete", headers=csrf(admin)).status_code == 200
    assert shown(c) == []
    with clean_db.connect() as con:
        paths = [r["detail"].get("path", "") for r in con.execute("SELECT detail FROM admin_log ORDER BY id")]
    assert any("announcements" in p and "delete" in p for p in paths) and sum("announcements" in p for p in paths) >= 2
