"""Login, roles, lock-out (SR33-SR36). Uses the TEST database.
The guide's tests (p. 63), rewritten in step 5.10 for the React site: the same behaviour is checked,
but the login is POST /api/login (with the CSRF token) and the admin pages are /admin (React) + /api/admin."""
import pytest
from fastapi.testclient import TestClient

PW = "a-long-password"


@pytest.fixture
def c(clean_db, monkeypatch, tmp_path):
    from app import api, main
    (tmp_path / "index.html").write_text("<div id=root></div>")        # a stand-in for the built React page
    monkeypatch.setattr(main, "FRONTEND", tmp_path)
    monkeypatch.setattr(main, "load_index", lambda: None)
    api.FAILED_BY_IP.clear()
    with TestClient(main.app) as client:
        yield client


def csrf(c):
    return {"X-CSRF-Token": c.get("/api/me").json()["csrf"]}


def log_in(c, email, password=PW):
    return c.post("/api/login", json={"email": email, "password": password}, headers=csrf(c))


def test_login_page_needs_no_login(c):
    assert c.get("/login").status_code == 200
    assert c.get("/api/me").json()["user"] is None


def test_admin_pages_refuse_visitors(c):                                          # SR35
    for url in ["/admin", "/admin/eval", "/admin/settings", "/admin/users", "/admin/questions"]:
        assert c.get(url).status_code == 401, url


def test_admin_can_log_in(c, clean_db):
    clean_db.create_user("boss@example.com", PW)
    assert log_in(c, "boss@example.com").status_code == 200
    assert c.get("/admin").status_code == 200
    assert c.get("/api/admin/home").status_code == 200


def test_lock_after_five_failures(c, clean_db):                                   # SR36
    clean_db.create_user("boss@example.com", PW)
    for _ in range(5):
        log_in(c, "boss@example.com", "wrong")
    r = log_in(c, "boss@example.com")
    # locked: even the right password is refused, with the same message as a wrong one (step 5.6)
    assert r.status_code == 401 and r.json()["detail"] == "Wrong email or password."
    assert c.get("/admin").status_code == 401


def test_disabled_account_loses_access(c, clean_db):
    clean_db.create_user("boss@example.com", PW)
    log_in(c, "boss@example.com")
    with clean_db.connect() as con:
        con.execute("UPDATE users SET active = FALSE")
    assert c.get("/admin").status_code == 403
    assert c.get("/api/admin/home").status_code == 403


def test_passwords_are_hashed(clean_db):                                          # SR34
    clean_db.create_user("boss@example.com", PW)
    with clean_db.connect() as con:
        h = con.execute("SELECT password_hash FROM users").fetchone()["password_hash"]
    assert h.startswith("$2") and PW not in h


def test_other_admin_pages_refuse_visitors(c):                                    # SR35
    for url in ["/admin/corpus", "/admin/analytics", "/admin/abstentions", "/admin/questions/edit",
                "/admin/eval/1", "/admin/eval/compare?a=1&b=2", "/api/admin/questions/export"]:
        assert c.get(url).status_code == 401, url


def test_admin_actions_refuse_visitors(c, clean_db):                              # SR35
    h = csrf(c)                                       # even with a valid token, a visitor is refused
    assert c.post("/api/admin/users", json={"email": "x@example.com", "password": PW, "role": "admin"},
                  headers=h).status_code == 401
    assert c.post("/api/admin/users/1/toggle", headers=h).status_code == 401
    assert c.post("/api/admin/eval/run", json={}, headers=h).status_code == 401
    assert c.post("/api/admin/reindex", json={"max_words": 350}, headers=h).status_code == 401
    with clean_db.connect() as con:
        assert con.execute("SELECT count(*) AS n FROM users").fetchone()["n"] == 0
