"""Free and paid accounts, questions per day (SPEC section 11, 2026-11-14; Dr. Salloum's request 7).
Written from the rule in SPEC and the test table Joe approved, before the code.
Fake search and fake model from tests/test_api_research.py; TEST database.
Most tests put the day's earlier questions straight into query_log (the rule counts them from there), so they do not
have to ask 100 questions through the page (which the 10-a-minute limit per address would stop anyway)."""
import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
from app import llm, logs
from tests.test_api_research import c, csrf, ask, logged, good_model   # noqa: F401  (c is the fixture)
from tests.test_visitor_accounts import sign_up, log_in, PW

READER = "reader@example.com"


@pytest.fixture
def reader(c, clean_db):
    """c logged in as a new 'user' account; returns its id."""
    from app import api
    api.SIGNUPS_BY_IP.clear()
    sign_up(c, READER)
    with clean_db.connect() as con:
        return con.execute("SELECT id FROM users WHERE email = %s", (READER,)).fetchone()["id"]


@pytest.fixture
def admin(c, clean_db):
    """Another browser, logged in as an administrator (after c: the fake search and model are set)."""
    from app import main
    clean_db.create_user("boss@example.com", PW)
    with TestClient(main.app, client=("203.0.113.9", 50000)) as a:
        log_in(a, "boss@example.com")
        yield a


def earlier_questions(clean_db, user_id, n, status="ANSWERED", demo=False, when="now()"):
    """n questions of this account already in query_log (when: an SQL time)."""
    details = Jsonb({"shown": {"demo": True}} if demo else {})
    with clean_db.connect() as con:
        for i in range(n):
            con.execute(f"INSERT INTO query_log (created_at, question, status, user_id, details) "
                        f"VALUES ({when}, %s, %s, %s, %s)", (f"Earlier question {i}", status, user_id, details))


def set_plan(admin, user_id, plan):
    return admin.post(f"/api/admin/users/{user_id}/plan", json={"plan": plan}, headers=csrf(admin))


def count_model_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "ask_model", lambda q, p, *a: calls.append(q) or good_model(q, p))
    return calls


def test_1_a_new_account_is_free(c, reader, clean_db):
    with clean_db.connect() as con:
        assert con.execute("SELECT plan FROM users WHERE id = %s", (reader,)).fetchone()["plan"] == "free"


def test_2_a_free_account_gets_10_questions_a_day(c, reader):
    for i in range(10):
        assert ask(c, f"Question number {i}").status_code == 200


def test_3_the_11th_question_of_a_free_account_is_refused_before_the_model(c, reader, clean_db, monkeypatch):
    earlier_questions(clean_db, reader, 10)
    calls = count_model_calls(monkeypatch)
    r = ask(c, "One question too many")
    assert r.status_code == 429
    assert "You have used your 10 questions for today (free plan)" in r.json()["detail"]
    assert "midnight" in r.json()["detail"]
    assert calls == []                                                   # no search, no model, no tokens
    assert "One question too many" not in [row["question"] for row in logged(clean_db)]


def test_4_the_refusal_goes_to_the_accounts_log(c, reader, clean_db):
    earlier_questions(clean_db, reader, 10)
    ask(c, "One question too many")
    refused = [row for row in logs.user_log(reader) if row["event"] == "refused"]
    assert len(refused) == 1 and refused[0]["detail"]["reason"] == "daily limit"


def test_5_a_paid_account_gets_100(c, reader, admin, clean_db):
    assert set_plan(admin, reader, "paid").status_code == 200
    earlier_questions(clean_db, reader, 10)
    assert ask(c, "The 11th question").status_code == 200
    earlier_questions(clean_db, reader, 89)                               # 100 today now
    r = ask(c, "The 101st question")
    assert r.status_code == 429 and "100 questions for today (paid plan)" in r.json()["detail"]


def test_6_yesterdays_questions_do_not_count(c, reader, clean_db):
    midnight = "(date_trunc('day', now() AT TIME ZONE 'Asia/Beirut') AT TIME ZONE 'Asia/Beirut')"
    earlier_questions(clean_db, reader, 10, when=f"{midnight} - interval '1 minute'")   # 23:59 yesterday, Beirut
    assert ask(c).status_code == 200


@pytest.mark.parametrize("kind", ["WELCOME", "ERROR", "demo"])
def test_7_greetings_errors_and_examples_do_not_count(c, reader, clean_db, kind):
    if kind == "demo":
        earlier_questions(clean_db, reader, 10, demo=True)
    else:
        earlier_questions(clean_db, reader, 10, status=kind)
    earlier_questions(clean_db, reader, 9)                                # 9 real answers: one left
    assert ask(c).status_code == 200
    assert ask(c, "Now the limit").status_code == 429


def test_8_an_administrator_has_no_daily_limit(admin, clean_db):
    with clean_db.connect() as con:
        boss = con.execute("SELECT id FROM users WHERE email = 'boss@example.com'").fetchone()["id"]
    earlier_questions(clean_db, boss, 150)
    assert ask(admin).status_code == 200


def test_9_switching_the_plan_is_logged(c, reader, admin):
    r = set_plan(admin, reader, "paid")
    assert r.status_code == 200
    [change] = [row for row in logs.user_log(reader) if row["event"] == "plan_change"]
    assert change["detail"] == {"from": "free", "to": "paid", "by": "boss@example.com"}
    assert any(row["action"] == f"POST /api/admin/users/{reader}/plan" and row["target_user_id"] == reader
               for row in logs.admin_log())


def test_10_wrong_plan_switches_are_refused(c, reader, admin, clean_db):
    with clean_db.connect() as con:
        boss = con.execute("SELECT id FROM users WHERE email = 'boss@example.com'").fetchone()["id"]
    assert set_plan(admin, boss, "paid").status_code == 400              # an administrator has no plan
    assert set_plan(admin, reader, "gold").status_code == 400            # unknown plan
    assert set_plan(admin, 9999, "paid").status_code == 404              # no such account
    assert c.post(f"/api/admin/users/{reader}/plan", json={"plan": "paid"},
                  headers=csrf(c)).status_code == 403                    # a 'user' cannot make itself paid
    with clean_db.connect() as con:
        assert con.execute("SELECT plan FROM users WHERE id = %s", (reader,)).fetchone()["plan"] == "free"


def test_11_an_administrator_changes_the_limits(c, reader, admin, clean_db):
    r = admin.post("/api/admin/limits", json={"free_daily_questions": 3, "paid_daily_questions": 100},
                   headers=csrf(admin))
    assert r.status_code == 200
    earlier_questions(clean_db, reader, 3)
    r = ask(c)
    assert r.status_code == 429 and "3 questions for today" in r.json()["detail"]
    for bad in (0, 1001):
        assert admin.post("/api/admin/limits", json={"free_daily_questions": bad, "paid_daily_questions": 100},
                          headers=csrf(admin)).status_code == 400


def test_12_me_gives_the_plan_and_the_questions_left(c, reader, clean_db):
    earlier_questions(clean_db, reader, 4)
    me = c.get("/api/me").json()
    assert me["plan"] == {"plan": "free", "daily_limit": 10, "left_today": 6}
