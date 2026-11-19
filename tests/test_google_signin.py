"""Sign in with Google (SPEC section 11, 2026-11-13): written from the rule in SPEC, before the code.
Google is never called: the check of the token (app/google_auth.verify_credential) is replaced by a fake that
knows a few made-up tokens. TEST database."""
import pytest
from tests.test_api_research import c as research_client, csrf   # noqa: F401  (the fixture is used below)

PW = "a-long-password"
CLIENT_ID = "1234-test.apps.googleusercontent.com"
TOKENS = {"good-reader": "reader@example.com", "good-boss": "boss@example.com"}   # token -> verified email


def fake_verify(credential):
    if credential not in TOKENS:
        raise ValueError("bad token")
    return TOKENS[credential]


@pytest.fixture
def c(research_client, clean_db, monkeypatch):
    from app import api, google_auth
    api.SIGNUPS_BY_IP.clear()
    monkeypatch.setattr(google_auth, "CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(google_auth, "verify_credential", fake_verify)
    clean_db.create_user("boss@example.com", PW)                          # an administrator
    return research_client


def google(c, credential="good-reader"):
    return c.post("/api/auth/google", json={"credential": credential}, headers=csrf(c))


def user_log(db, email):
    with db.connect() as con:
        return [(r["event"], r["detail"]) for r in con.execute(
            "SELECT event, detail FROM user_log l JOIN users u ON u.id = l.user_id WHERE u.email = %s ORDER BY l.id",
            (email,))]


def test_the_page_gets_the_client_id(c):                                   # rule 6
    assert c.get("/api/me").json()["google_client_id"] == CLIENT_ID


def test_a_new_email_makes_a_user_account_and_logs_it_in(c, clean_db):     # rules 3 and 5
    r = google(c)
    assert r.status_code == 200 and r.json()["user"] == {"email": "reader@example.com", "role": "user"}
    assert c.get("/api/me").json()["user"] == {"email": "reader@example.com", "role": "user"}
    assert user_log(clean_db, "reader@example.com") == [("signup", {"method": "google"})]


def test_nobody_knows_the_password_of_a_google_account(c, clean_db):       # rule 3
    google(c)
    c.post("/api/logout", headers=csrf(c))
    for guess in ["", PW, "reader@example.com"]:
        assert c.post("/api/login", json={"email": "reader@example.com", "password": guess},
                      headers=csrf(c)).status_code == 401


def test_an_existing_user_account_is_logged_into_not_copied(c, clean_db):  # rule 3
    uid = clean_db.create_visitor("reader@example.com", PW)
    assert google(c).status_code == 200
    with clean_db.connect() as con:
        assert con.execute("SELECT count(*) AS n FROM users WHERE email = 'reader@example.com'").fetchone()["n"] == 1
    assert c.get("/api/history").status_code == 200                       # logged in as that account
    assert user_log(clean_db, "reader@example.com") == [("login", {"method": "google"})]
    c.post("/api/logout", headers=csrf(c))                                # its own password still works
    assert c.post("/api/login", json={"email": "reader@example.com", "password": PW},
                  headers=csrf(c)).json()["user"]["role"] == "user"
    assert clean_db.active_role(uid) == "user"


def test_an_administrator_cannot_use_google(c, clean_db):                  # rules 4 and 5
    r = google(c, "good-boss")
    assert r.status_code == 403 and "password" in r.json()["detail"]
    assert c.get("/api/me").json()["user"] is None
    assert c.get("/api/admin/settings").status_code == 401
    with clean_db.connect() as con:
        row = con.execute("SELECT admin_email, action FROM admin_log ORDER BY id DESC LIMIT 1").fetchone()
    assert (row["admin_email"], row["action"]) == ("boss@example.com", "login_failed")


def test_a_disabled_account_is_refused(c, clean_db):                       # rule 4
    clean_db.create_visitor("reader@example.com", PW)
    with clean_db.connect() as con:
        con.execute("UPDATE users SET active = FALSE WHERE email = 'reader@example.com'")
    assert google(c).status_code == 403
    assert c.get("/api/me").json()["user"] is None


def test_a_bad_token_saves_nothing(c, clean_db):                           # rule 4
    assert google(c, "forged").status_code == 401
    with clean_db.connect() as con:
        assert con.execute("SELECT count(*) AS n FROM users").fetchone()["n"] == 1    # only the administrator


def test_the_route_needs_the_csrf_token(c):                                # rule 1
    assert c.post("/api/auth/google", json={"credential": "good-reader"}).status_code == 403


def test_google_sign_ups_count_in_the_limit_per_address(c, monkeypatch):   # rule 3
    for k in range(5):
        assert c.post("/api/signup", json={"email": f"r{k}@example.com", "password": PW},
                      headers=csrf(c)).status_code == 200
        c.post("/api/logout", headers=csrf(c))
    assert google(c).status_code == 429


def test_without_a_client_id_there_is_no_google_sign_in(c, monkeypatch):   # rule 6
    from app import google_auth
    monkeypatch.setattr(google_auth, "CLIENT_ID", "")
    assert c.get("/api/me").json()["google_client_id"] is None
    assert google(c).status_code == 404


def test_only_a_verified_email_from_our_client_is_accepted(monkeypatch):   # rule 2, the real check
    from app import google_auth
    seen = {}

    def fake_google(token, request, audience):                            # stands for Google's public-key check
        seen["audience"] = audience
        return {"good": {"email": "Reader@Example.com", "email_verified": True},
                "unverified": {"email": "x@example.com", "email_verified": False}}[token]
    monkeypatch.setattr(google_auth, "CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(google_auth.id_token, "verify_oauth2_token", fake_google)
    assert google_auth.verify_credential("good") == "reader@example.com"
    assert seen["audience"] == CLIENT_ID                                   # the token must be made for us
    with pytest.raises(ValueError):
        google_auth.verify_credential("unverified")
