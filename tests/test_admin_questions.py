"""Admin pages: every question asked, and the admin log (SPEC section 11, 2026-11-14; part 2).
Written from the rule in SPEC and the test table Joe approved, before the code. Fake search and model; TEST database."""
import pytest
from fastapi.testclient import TestClient
from tests.test_api_research import c, csrf, ask   # noqa: F401  (c is the fixture)
from tests.test_visitor_accounts import sign_up, log_in, PW


@pytest.fixture
def asked(c, clean_db):
    """A visitor's question, then reader@example.com's 2 questions (one NOT_SUPPORTED). Returns the reader's id."""
    from app import api, llm
    api.SIGNUPS_BY_IP.clear()
    ask(c, "A visitor asks about immunity")                         # the visitor's one question
    sign_up(c, "reader@example.com")
    ask(c, "Is the President immune from prosecution?")
    good = llm.ask_model
    llm.ask_model = lambda q, p, *a: {"status": "SUPPORTED", "sentences": [
        {"text": "See Fake v. Case, 999 U.S. 9999.", "sources": ["P1"], "quote": "x"}]}
    try:
        ask(c, "What about Fake v. Case?")                          # removed by the verifier: NOT_SUPPORTED
    finally:
        llm.ask_model = good
    with clean_db.connect() as con:
        return con.execute("SELECT id FROM users WHERE email = 'reader@example.com'").fetchone()["id"]


@pytest.fixture
def admin(c, clean_db):
    from app import main
    clean_db.create_user("boss@example.com", PW)
    with TestClient(main.app, client=("203.0.113.9", 50000)) as a:
        log_in(a, "boss@example.com")
        yield a


def questions(admin, query=""):
    r = admin.get("/api/admin/all-questions" + query)
    assert r.status_code == 200, r.text
    return r.json()


def test_1_every_question_newest_first_with_who_asked(asked, admin):
    d = questions(admin)
    assert d["total"] == 3
    assert [q["question"] for q in d["rows"]] == ["What about Fake v. Case?", "Is the President immune from prosecution?",
                                                 "A visitor asks about immunity"]
    assert [q["email"] for q in d["rows"]] == ["reader@example.com", "reader@example.com", None]
    assert d["rows"][0]["user_id"] == asked and d["rows"][0]["chat_id"] and d["rows"][0]["status"] == "NOT_SUPPORTED"


def test_2_filters(asked, admin):
    assert [q["question"] for q in questions(admin, "?status=NOT_SUPPORTED")["rows"]] == ["What about Fake v. Case?"]
    assert [q["question"] for q in questions(admin, "?who=visitors")["rows"]] == ["A visitor asks about immunity"]
    assert questions(admin, f"?who={asked}")["total"] == 2
    assert [q["question"] for q in questions(admin, "?q=PRESIDENT")["rows"]] == ["Is the President immune from prosecution?"]
    assert questions(admin, f"?who={asked}&q=immun")["total"] == 1       # combined
    assert admin.get("/api/admin/all-questions?status=MAYBE").status_code == 400
    assert admin.get("/api/admin/all-questions?who=someone").status_code == 400


def test_3_100_per_page(c, clean_db, admin):
    with clean_db.connect() as con:
        for i in range(130):
            con.execute("INSERT INTO query_log (question, status) VALUES (%s, 'ANSWERED')", (f"Question {i}",))
    first, second = questions(admin), questions(admin, "?page=2")
    assert first["total"] == 130 and len(first["rows"]) == 100 and len(second["rows"]) == 30
    assert first["rows"][0]["question"] == "Question 129" and second["rows"][-1]["question"] == "Question 0"


def test_4_one_question_with_the_answer_as_shown(asked, admin):
    top = questions(admin)["rows"][1]                                # the answered one
    d = admin.get(f"/api/admin/all-questions/{top['id']}").json()
    assert d["question"] == "Is the President immune from prosecution?" and d["email"] == "reader@example.com"
    assert d["shown"]["status"] == "ANSWERED" and d["shown"]["sentences"] and d["reason"] is not None
    assert admin.get("/api/admin/all-questions/99999").status_code == 404


def test_5_the_admin_log_and_its_csv(admin):
    rows = admin.get("/api/admin/log").json()
    assert any(r["action"] == "login" and r["admin_email"] == "boss@example.com" for r in rows)
    csv = admin.get("/api/admin/log?format=csv")
    assert csv.headers["content-type"].startswith("text/csv") and "boss@example.com" in csv.text


def test_6_only_administrators(c, asked):
    from app import main
    assert c.get("/api/admin/all-questions").status_code == 403               # c is logged in as the reader
    with TestClient(main.app) as visitor:
        assert visitor.get("/api/admin/all-questions").status_code == 401
        assert visitor.get("/api/admin/all-questions/1").status_code == 401
