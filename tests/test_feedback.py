"""Feedback on an answer (SPEC 11, 2026-11-20, from CedarPay's reviews), written from the rule before the code.
Fake search and model from tests/test_api_research.py; TEST database."""
import pytest
from fastapi.testclient import TestClient
from tests.test_api_research import c as research_client, csrf, ask   # noqa: F401  (the fixture is used below)
from tests.test_visitor_accounts import sign_up, log_in, PW


@pytest.fixture
def c(research_client):
    from app import api
    api.SIGNUPS_BY_IP.clear()
    return research_client


@pytest.fixture
def other(c):
    """A second browser (another session, another address)."""
    from app import main
    with TestClient(main.app, client=("203.0.113.7", 50001)) as o:
        yield o


def rate(client, qid, helpful=False, reason=None, comment=None):
    body = {"query_id": qid, "helpful": helpful, "reason": reason, "comment": comment}
    return client.post("/api/feedback", json={k: v for k, v in body.items() if v is not None}, headers=csrf(client))


def ratings(clean_db):
    with clean_db.connect() as con:
        return con.execute("SELECT * FROM answer_feedback ORDER BY query_id").fetchall()


def test_a_visitor_rates_its_own_answer_and_nobody_else_can(c, other, clean_db):
    qid = ask(c).json()["id"]
    assert rate(c, qid, helpful=False, reason="missed_holding", comment="It quoted the dissent.").status_code == 200
    row = ratings(clean_db)[0]
    assert (row["helpful"], row["reason"], row["comment"], row["user_id"]) == (False, "missed_holding",
                                                                               "It quoted the dissent.", None)
    assert rate(other, qid, helpful=True).status_code == 404       # another browser: not its answer
    assert rate(c, 999999, helpful=True).status_code == 404        # no such answer


def test_an_account_rates_its_answers_not_another_accounts(c, other, clean_db):
    sign_up(c, "reader@example.com")
    qid = ask(c).json()["id"]
    assert rate(c, qid, helpful=True).status_code == 200
    sign_up(other, "someone@example.com")
    assert rate(other, qid, helpful=False).status_code == 404
    assert ratings(clean_db)[0]["user_id"] is not None


def test_rating_again_changes_the_rating(c, clean_db):
    qid = ask(c).json()["id"]
    rate(c, qid, helpful=False, reason="incomplete")
    rate(c, qid, helpful=True)
    rows = ratings(clean_db)
    assert len(rows) == 1 and rows[0]["helpful"] is True and rows[0]["reason"] is None


@pytest.mark.parametrize("body", [{"reason": "it is bad"}, {"comment": "x" * 501}])
def test_an_unknown_reason_or_a_long_comment_is_refused(c, clean_db, body):
    qid = ask(c).json()["id"]
    assert rate(c, qid, helpful=False, **body).status_code == 400 and ratings(clean_db) == []


def test_an_error_has_nothing_to_rate(c, clean_db, monkeypatch):
    from app import llm

    def broken(*a, **k):
        raise llm.ModelError("down")
    monkeypatch.setattr(llm, "ask_model", broken)
    r = ask(c)
    assert r.json()["status"] == "ERROR"
    assert rate(c, r.json()["id"], helpful=False).status_code == 400


def test_the_admin_page_shows_the_counts_and_the_latest_ratings(c, other, clean_db):
    sign_up(c, "reader@example.com")
    first, second = ask(c).json()["id"], ask(c, "What about unofficial acts?").json()["id"]
    rate(c, first, helpful=True)
    rate(c, second, helpful=False, reason="wrong_case", comment="Not this case")
    assert other.get("/api/admin/feedback").status_code == 401    # administrators only
    clean_db.create_user("boss@example.com", PW)
    log_in(other, "boss@example.com")
    data = other.get("/api/admin/feedback").json()
    assert data["counts"] == {"helpful": 1, "not_helpful": 1, "by_reason": {"wrong_case": 1}}
    latest = data["latest"][0]
    assert latest["query_id"] == second and latest["comment"] == "Not this case"
    assert latest["question"] == "What about unofficial acts?" and latest["email"] == "reader@example.com"
