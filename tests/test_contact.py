"""The contact form and the site information (app/api_site.py), written from the expected behaviour before the code.
A visitor (no account, SR33) can send a message; it is kept in contact_messages with no deletion date (team decision,
2026-11-12, written in the privacy policy); an administrator reads and deletes messages. TEST database."""
import pytest
from fastapi.testclient import TestClient

PW = "a-long-password"
GOOD = {"name": "A. Visitor", "email": "visitor@example.com", "message": "Your site helped me find Bostock, thank you."}


@pytest.fixture
def c(clean_db, monkeypatch):
    from app import api, api_site, main
    monkeypatch.setattr(main, "load_index", lambda: None)
    api.FAILED_BY_IP.clear()
    api_site.SENT_BY_IP.clear()
    clean_db.create_user("boss@example.com", PW)
    with TestClient(main.app) as client:
        yield client


def csrf(c):
    return {"X-CSRF-Token": c.get("/api/me").json()["csrf"]}


def send(c, body=GOOD, headers=None):
    return c.post("/api/contact", json=body, headers=csrf(c) if headers is None else headers)


def stored(clean_db):
    with clean_db.connect() as con:
        return con.execute("SELECT name, email, message FROM contact_messages ORDER BY id").fetchall()


def test_a_visitor_sends_a_message_without_an_account(c, clean_db):
    assert send(c).status_code == 200
    assert stored(clean_db) == [GOOD]
    assert c.get("/api/me").json()["user"] is None


def test_a_message_needs_the_csrf_token(c, clean_db):
    assert send(c, headers={}).status_code == 403 and send(c, headers={"X-CSRF-Token": "made-up"}).status_code == 403
    assert stored(clean_db) == []


@pytest.mark.parametrize("change", [{"email": "not-an-email"}, {"email": "no-dot@example"}, {"email": "a b@example.com"},
                                    {"message": "   "}, {"message": "x" * 5001}, {"name": "n" * 101}, {"name": ""}])
def test_a_bad_message_is_refused_with_a_reason(c, clean_db, change):
    r = send(c, {**GOOD, **change})
    assert r.status_code == 400 and r.json()["detail"] and stored(clean_db) == []


def test_at_most_three_messages_per_address_in_ten_minutes(c, clean_db):
    assert [send(c).status_code for _ in range(3)] == [200, 200, 200]
    r = send(c)
    assert r.status_code == 429 and "minute" in r.json()["detail"] and len(stored(clean_db)) == 3


def test_the_site_information_gives_the_contact_email_from_the_settings(c, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "CONTACT_EMAIL", "team@example.org")
    assert c.get("/api/site").json()["contact_email"] == "team@example.org"
    monkeypatch.setattr(config, "CONTACT_EMAIL", "")
    assert c.get("/api/site").json()["contact_email"] is None             # not set: the page shows no address


def test_an_administrator_reads_the_messages_newest_first_and_deletes_one(c, clean_db):
    send(c, {**GOOD, "message": "First message, long enough."})
    send(c, {**GOOD, "message": "Second message, long enough."})
    assert c.post("/api/login", json={"email": "boss@example.com", "password": PW}, headers=csrf(c)).status_code == 200
    messages = c.get("/api/admin/messages").json()
    assert [m["message"] for m in messages] == ["Second message, long enough.", "First message, long enough."]
    left = c.post(f"/api/admin/messages/{messages[0]['id']}/delete", headers=csrf(c)).json()
    assert [m["message"] for m in left] == ["First message, long enough."]
