"""Admin pages: every account with its details, and one account's details (SPEC section 11, 2026-11-14; part 2).
Written from the rule in SPEC and the test table Joe approved, before the code. Fake search and model; TEST database."""
import pytest
from fastapi.testclient import TestClient
from app import exports, logs
from tests.test_api_research import c, csrf, ask   # noqa: F401  (c is the fixture)
from tests.test_visitor_accounts import sign_up, log_in, log_out, PW

DETAILS = {"email", "role", "plan", "active", "locked_until", "created_at", "last_login", "logins", "last_activity",
           "questions"}


@pytest.fixture
def reader(c, clean_db):
    """reader@example.com: signed up, 2 questions in one chat, logged out and in again. Returns its id."""
    from app import api
    api.SIGNUPS_BY_IP.clear()
    sign_up(c, "reader@example.com")
    chat = ask(c).json()["chat_id"]
    c.post("/api/ask", json={"question": "And his private acts?", "chat_id": chat}, headers=csrf(c))
    log_out(c)
    log_in(c, "reader@example.com")
    log_out(c)
    with clean_db.connect() as con:
        return con.execute("SELECT id FROM users WHERE email = 'reader@example.com'").fetchone()["id"]


@pytest.fixture
def admin(c, clean_db):
    from app import main
    clean_db.create_user("boss@example.com", PW)
    with TestClient(main.app, client=("203.0.113.9", 50000)) as a:
        log_in(a, "boss@example.com")
        yield a


def test_1_the_list_has_every_account_with_its_details(reader, admin):
    rows = {u["email"]: u for u in admin.get("/api/admin/users").json()}
    assert set(rows) == {"reader@example.com", "boss@example.com"}           # visitors' accounts too
    r = rows["reader@example.com"]
    assert DETAILS <= set(r) and "password_hash" not in r
    assert r["role"] == "user" and r["plan"] == "free" and r["questions"] == 2 and r["logins"] == 1
    assert r["created_at"] and r["last_login"] and r["last_activity"]


def test_2_the_figures_are_the_same_as_in_the_pdf(reader, admin):
    page = {u["email"]: u for u in admin.get("/api/admin/users").json()}
    for s in exports.summaries():
        for k in ("logins", "questions"):
            assert page[s["email"]][k] == s[k]


def test_3_one_accounts_details_questions_chats_and_log(reader, admin):
    d = admin.get(f"/api/admin/users/{reader}").json()
    assert d["user"]["email"] == "reader@example.com" and d["user"]["questions"] == 2
    assert [q["question"] for q in d["questions"]] == ["And his private acts?", "Is the President immune from prosecution?"]
    assert d["questions"][0]["chat_id"] == d["questions"][1]["chat_id"]
    assert [(ch["title"], ch["questions"]) for ch in d["chats"]] == [("Is the President immune from prosecution?", 2)]
    events = [row["event"] for row in d["log"]]
    assert events[0] == "logout" and events[-1] == "signup" and "follow_up" in events


def test_3b_an_administrators_log_is_what_they_did(reader, admin, clean_db):
    with clean_db.connect() as con:
        boss = con.execute("SELECT id FROM users WHERE email = 'boss@example.com'").fetchone()["id"]
    d = admin.get(f"/api/admin/users/{boss}").json()
    assert d["user"]["role"] == "admin" and any(row["action"] == "login" for row in d["log"])


def test_4_unknown_account(admin):
    assert admin.get("/api/admin/users/99999").status_code == 404


def test_5_only_administrators(c, reader):
    from app import main
    log_in(c, "reader@example.com")
    assert c.get(f"/api/admin/users/{reader}").status_code == 403
    with TestClient(main.app) as visitor:
        assert visitor.get(f"/api/admin/users/{reader}").status_code == 401


def test_6_reading_an_accounts_details_is_in_the_admin_log(reader, admin):
    admin.get(f"/api/admin/users/{reader}")
    assert any(row["action"] == f"GET /api/admin/users/{reader}" and row["target_user_id"] == reader
               and row["admin_email"] == "boss@example.com" for row in logs.admin_log())
