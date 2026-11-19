"""Visitor accounts (SPEC section 11, 2026-11-12): written from the rule in SPEC, not from the code.
A visitor may sign up to keep their question history; the research page stays open without an account (SR33).
Fake search and fake model from tests/test_api_research.py; TEST database."""
import pytest
from tests.test_api_research import c as research_client, csrf, ask   # noqa: F401  (the fixture is used below)

PW = "a-long-password"


@pytest.fixture
def c(research_client):
    from app import api
    api.SIGNUPS_BY_IP.clear()                       # each test starts with no sign-ups counted
    return research_client


def sign_up(c, email="reader@example.com", password=PW):
    return c.post("/api/signup", json={"email": email, "password": password}, headers=csrf(c))


def log_in(c, email, password=PW):
    return c.post("/api/login", json={"email": email, "password": password}, headers=csrf(c))


def log_out(c):
    c.post("/api/logout", headers=csrf(c))


def test_sign_up_makes_a_user_and_logs_it_in(c, clean_db):                   # rules 1 and 5
    r = sign_up(c, "Reader@Example.com ")
    assert r.status_code == 200 and r.json()["user"] == {"email": "reader@example.com", "role": "user"}
    assert c.get("/api/me").json()["user"] == {"email": "reader@example.com", "role": "user"}
    with clean_db.connect() as con:
        row = con.execute("SELECT role, password_hash FROM users WHERE email = 'reader@example.com'").fetchone()
    assert row["role"] == "user" and row["password_hash"] != PW                # stored as a hash only
    log_out(c)
    assert log_in(c, "reader@example.com").json()["user"]["role"] == "user"   # the login page sends it to /research


def test_sign_up_never_changes_an_existing_account(c, clean_db):             # rule 2
    clean_db.create_user("boss@example.com", PW)                           # an administrator
    r = sign_up(c, "boss@example.com", "another-long-password")
    assert r.status_code == 409 and "already exists" in r.json()["detail"]
    assert c.get("/api/me").json()["user"] is None                          # not logged in as the admin
    assert log_in(c, "boss@example.com").json()["user"]["role"] == "admin"  # old password and role unchanged


@pytest.mark.parametrize("email, password", [("reader@example.com", "short"),     # rule 3
                                             ("not-an-email", PW), ("reader@nodot", PW), ("", PW)])
def test_bad_sign_ups_are_refused_and_save_nothing(c, clean_db, email, password):
    assert sign_up(c, email, password).status_code == 400
    with clean_db.connect() as con:
        assert con.execute("SELECT count(*) AS n FROM users").fetchone()["n"] == 0


def test_sign_up_needs_the_csrf_token(c, clean_db):
    r = c.post("/api/signup", json={"email": "reader@example.com", "password": PW})
    assert r.status_code == 403


def test_at_most_five_accounts_per_address_per_hour(c):                      # rule 4
    for k in range(5):
        assert sign_up(c, f"reader{k}@example.com").status_code == 200
    assert sign_up(c, "reader5@example.com").status_code == 429


def test_a_user_cannot_reach_the_admin_pages(c):                             # rule 7, SR35
    sign_up(c)
    for path in ["/api/admin/users", "/api/admin/settings", "/api/admin/home", "/api/admin/eval"]:
        assert c.get(path).status_code == 403, path


def test_history_shows_only_your_own_questions(c, clean_db):                 # rule 6
    sign_up(c, "other@example.com")
    ask(c, "A question from another account")
    log_out(c)
    ask(c, "A question from a visitor without an account")
    sign_up(c, "reader@example.com")
    ask(c, "Is the President immune from prosecution?")
    ask(c, "What did the Court say about official acts?")
    mine = c.get("/api/history").json()
    assert [q["question"] for q in mine] == ["What did the Court say about official acts?",   # newest first
                                             "Is the President immune from prosecution?"]
    with clean_db.connect() as con:
        theirs = con.execute("SELECT id FROM query_log WHERE question LIKE 'A question from%'").fetchall()
    for q in theirs:                                                       # another account's, a visitor's: 404
        assert c.get(f"/api/history/{q['id']}").status_code == 404


def test_one_of_your_questions_comes_back_as_it_was_shown(c):
    sign_up(c)
    shown = ask(c).json()
    back = c.get(f"/api/history/{shown['id']}").json()
    assert back["question"] == "Is the President immune from prosecution?"
    assert back["shown"]["status"] == shown["status"] and back["shown"]["sentences"] == shown["sentences"]


def test_no_history_without_an_account(c):
    ask(c)                                                                 # still allowed without an account (SR33)
    assert c.get("/api/history").status_code == 401
    assert c.get("/api/history/1").status_code == 401


def test_a_disabled_user_loses_the_history_at_once(c, clean_db):
    sign_up(c)
    ask(c)
    with clean_db.connect() as con:
        con.execute("UPDATE users SET active = FALSE WHERE email = 'reader@example.com'")
    assert c.get("/api/history").status_code == 403


def test_the_start_keeps_the_user_accounts(clean_db):                        # rule 8
    uid = clean_db.create_visitor("reader@example.com", PW)
    clean_db.init_db()                                                     # runs the start-up migrations again
    assert clean_db.active_role(uid) == "user"
