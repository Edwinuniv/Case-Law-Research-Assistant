"""The JSON API's login, logout, roles and CSRF (step 5.6, SR33-SR36). Uses the TEST database."""
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

PW = "a-long-password"


@pytest.fixture
def c(clean_db):
    from app import api
    from app.main import app
    api.FAILED_BY_IP.clear()                     # each test starts with no failed logins
    with TestClient(app) as client:
        yield client


def csrf(c):
    return {"X-CSRF-Token": c.get("/api/me").json()["csrf"]}


def log_in(c, email, password=PW):
    return c.post("/api/login", json={"email": email, "password": password}, headers=csrf(c))


# a protected GET and POST per role, added only for these tests (the real routes come in 5.7 and 5.9)
def add_test_routes():
    from app import api
    from app.main import app
    if any(getattr(r, "path", "") == "/api/test/admin" for r in app.routes):
        return

    @app.get("/api/test/user")
    def for_users(user=Depends(api.require_user)):
        return user

    @app.get("/api/test/admin")
    def for_admins(user=Depends(api.require_admin)):
        return user

    @app.post("/api/test/admin-action", dependencies=[Depends(api.check_csrf)])
    def admin_action(user=Depends(api.require_admin)):
        return {"done": True}


def test_me_without_login(c):
    r = c.get("/api/me").json()
    assert r["user"] is None and len(r["csrf"]) > 20
    assert "2000" in r["coverage"] and len(r["examples"]) >= 2              # SR30


def test_user_and_admin_can_log_in(c, clean_db):
    clean_db.create_user("reader@example.com", PW, role="user")
    r = log_in(c, "reader@example.com")
    assert r.status_code == 200 and r.json()["user"] == {"email": "reader@example.com", "role": "user"}
    assert c.get("/api/me").json()["user"]["role"] == "user"


def test_login_error_is_generic(c, clean_db):
    clean_db.create_user("boss@example.com", PW)
    unknown = log_in(c, "nobody@example.com")
    wrong = log_in(c, "boss@example.com", "wrong")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json() == {"detail": "Wrong email or password."}


def test_login_without_csrf_token_is_refused(c, clean_db):
    clean_db.create_user("boss@example.com", PW)
    r = c.post("/api/login", json={"email": "boss@example.com", "password": PW})
    assert r.status_code == 403
    r = c.post("/api/login", json={"email": "boss@example.com", "password": PW},
               headers={"X-CSRF-Token": "made-up"})
    assert r.status_code == 403
    assert c.get("/api/me").json()["user"] is None


def test_post_without_csrf_token_is_refused_when_logged_in(c, clean_db):
    add_test_routes()
    clean_db.create_user("boss@example.com", PW)
    log_in(c, "boss@example.com")
    assert c.post("/api/test/admin-action").status_code == 403
    assert c.post("/api/test/admin-action", headers=csrf(c)).status_code == 200


def test_new_csrf_token_after_login(c, clean_db):
    clean_db.create_user("boss@example.com", PW)
    before = c.get("/api/me").json()["csrf"]
    after = log_in(c, "boss@example.com").json()["csrf"]
    assert before != after
    assert c.post("/api/logout", headers={"X-CSRF-Token": before}).status_code == 403    # the old one is dead


def test_roles_are_checked_on_the_server(c, clean_db):                       # SR35, NFR8
    add_test_routes()
    assert c.get("/api/test/user").status_code == 401
    assert c.get("/api/test/admin").status_code == 401
    clean_db.create_user("reader@example.com", PW, role="user")
    log_in(c, "reader@example.com")
    assert c.get("/api/test/user").status_code == 200
    assert c.get("/api/test/admin").status_code == 403
    assert c.post("/api/test/admin-action", headers=csrf(c)).status_code == 403


def test_admin_reaches_admin_routes(c, clean_db):
    add_test_routes()
    clean_db.create_user("boss@example.com", PW)
    log_in(c, "boss@example.com")
    assert c.get("/api/test/admin").status_code == 200


def test_disabled_account_loses_access_at_once(c, clean_db):
    add_test_routes()
    clean_db.create_user("reader@example.com", PW, role="user")
    log_in(c, "reader@example.com")
    with clean_db.connect() as con:
        con.execute("UPDATE users SET active = FALSE")
    assert c.get("/api/test/user").status_code == 403
    with clean_db.connect() as con:
        con.execute("UPDATE users SET active = TRUE")
    assert c.get("/api/test/user").status_code == 401             # the session was cleared


def test_role_change_applies_at_once(c, clean_db):
    """The role comes from the database at each request, not from the cookie."""
    add_test_routes()
    clean_db.create_user("boss@example.com", PW)
    log_in(c, "boss@example.com")
    with clean_db.connect() as con:
        con.execute("UPDATE users SET role = 'user'")
    assert c.get("/api/test/admin").status_code == 403


def test_logout_clears_the_session(c, clean_db):
    add_test_routes()
    clean_db.create_user("reader@example.com", PW, role="user")
    log_in(c, "reader@example.com")
    assert c.post("/api/logout", headers=csrf(c)).status_code == 200
    assert c.get("/api/test/user").status_code == 401
    assert c.get("/api/me").json()["user"] is None


def test_too_many_failures_from_one_address(c, clean_db):
    from app import api
    clean_db.create_user("boss@example.com", PW)
    for i in range(api.LOGIN_LIMIT_PER_IP):                  # different emails: no account gets locked
        assert log_in(c, f"guess{i}@example.com").status_code == 401
    assert log_in(c, "boss@example.com").status_code == 429  # even the right password, from this address


def test_success_does_not_count_as_failure(c, clean_db):
    from app import api
    clean_db.create_user("boss@example.com", PW)
    for _ in range(api.LOGIN_LIMIT_PER_IP + 2):
        assert log_in(c, "boss@example.com").status_code == 200


def test_session_cookie_is_httponly(c, clean_db):
    clean_db.create_user("boss@example.com", PW)
    r = log_in(c, "boss@example.com")
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
