"""Saved answers (SPEC 11, 2026-11-20, from CedarPay), written from the rule before the code. TEST database."""
import pytest
from fastapi.testclient import TestClient
from tests.test_api_research import c as research_client, csrf, ask   # noqa: F401  (the fixture is used below)
from tests.test_visitor_accounts import sign_up, PW


@pytest.fixture
def c(research_client):
    from app import api
    api.SIGNUPS_BY_IP.clear()
    return research_client


def save(client, qid, saved=True):
    return client.post("/api/bookmarks", json={"query_id": qid, "saved": saved}, headers=csrf(client))


def test_an_account_saves_and_unsaves_its_answers(c, clean_db):
    sign_up(c, "reader@example.com")
    first, second = ask(c).json()["id"], ask(c, "What about unofficial acts?").json()["id"]
    assert save(c, first).json() == {"saved": True}
    save(c, second)
    listed = c.get("/api/bookmarks").json()
    assert [b["query_id"] for b in listed] == [second, first]                  # newest saved first
    assert listed[0]["question"] == "What about unofficial acts?"
    assert save(c, first, saved=False).json() == {"saved": False}
    assert [b["query_id"] for b in c.get("/api/bookmarks").json()] == [second]


def test_saving_twice_keeps_one(c, clean_db):
    sign_up(c, "reader@example.com")
    qid = ask(c).json()["id"]
    save(c, qid)
    save(c, qid)
    assert len(c.get("/api/bookmarks").json()) == 1


def test_a_saved_answer_opens_as_it_was_shown_without_asking_again(c, clean_db, monkeypatch):
    from app import llm
    sign_up(c, "reader@example.com")
    a = ask(c).json()
    save(c, a["id"])
    monkeypatch.setattr(llm, "ask_model", lambda *x, **k: (_ for _ in ()).throw(AssertionError("no model call")))
    opened = c.get(f"/api/answers/{a['id']}").json()
    assert opened["question"] == a["question"] and opened["sentences"] == a["sentences"]


def test_visitors_cannot_save_and_nobody_saves_another_accounts_answer(c, clean_db):
    from app import main
    qid = ask(c).json()["id"]
    assert save(c, qid).status_code == 401                                     # a visitor
    with TestClient(main.app, client=("203.0.113.7", 50001)) as other:
        sign_up(other, "someone@example.com")
        assert save(other, qid).status_code == 404
        assert other.get(f"/api/answers/{qid}").status_code == 404


def test_at_most_200_saved_answers(c, clean_db):
    sign_up(c, "reader@example.com")
    qid = ask(c).json()["id"]
    uid = clean_db.connect().execute("SELECT id FROM users WHERE email = 'reader@example.com'").fetchone()["id"]
    with clean_db.connect() as con:                                            # 200 saved answers already
        for _ in range(200):
            q = con.execute("INSERT INTO query_log (question, status, user_id) VALUES ('q', 'ANSWERED', %s) "
                            "RETURNING id", (uid,)).fetchone()["id"]
            con.execute("INSERT INTO bookmarks (user_id, query_id) VALUES (%s, %s)", (uid, q))
    r = save(c, qid)
    assert r.status_code == 400 and "200" in r.json()["detail"]


def test_deleting_the_account_deletes_its_saved_answers(c, clean_db):
    sign_up(c, "reader@example.com")
    save(c, ask(c).json()["id"])
    c.post("/api/account/delete", json={"password": PW}, headers=csrf(c))
    with clean_db.connect() as con:
        assert con.execute("SELECT count(*) AS n FROM bookmarks").fetchone()["n"] == 0
