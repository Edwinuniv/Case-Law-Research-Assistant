"""One question for a visitor without an account (SPEC section 11, 2026-11-14; Dr. Salloum's request 2).
Written from the rule in SPEC and the test table Joe approved, before the code.
Fake search and fake model from tests/test_api_research.py; TEST database."""
import pytest
from fastapi.testclient import TestClient
from app import llm
from tests.test_api_research import c, csrf, ask, logged, good_model   # noqa: F401  (c is the fixture)
from tests.test_visitor_accounts import sign_up, log_in, PW

REFUSED = "You have used your free question"


def count_model_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "ask_model", lambda q, p, *a: calls.append(q) or good_model(q, p))
    return calls


def test_1_a_visitor_gets_an_answer_to_the_first_question(c, clean_db):
    r = ask(c)
    assert r.status_code == 200 and r.json()["status"] == "ANSWERED"
    [row] = logged(clean_db)
    assert row["user_id"] is None                                   # logged for the admins, anonymous (FR28)


def test_2_the_second_question_is_refused_before_the_model(c, monkeypatch):
    ask(c)
    calls = count_model_calls(monkeypatch)
    r = ask(c, "And what about his private acts?")
    assert r.status_code == 403 and REFUSED in r.json()["detail"] and "Log in or sign up" in r.json()["detail"]
    assert calls == []                                              # no search, no model, no tokens


def test_3_the_refused_question_is_not_saved(c, clean_db):
    ask(c)
    ask(c, "And what about his private acts?")
    assert [row["question"] for row in logged(clean_db)] == ["Is the President immune from prosecution?"]


def test_4_another_browser_has_its_own_question(c):
    from app import main
    ask(c)
    with TestClient(main.app) as other:                             # a new cookie = a new session
        assert ask(other).status_code == 200
    assert ask(c, "Again?").status_code == 403


def test_5_a_question_refused_by_sr3_does_not_count(c):
    assert ask(c, "x" * 5000).status_code == 400
    assert ask(c).status_code == 200


def test_6_a_greeting_does_not_count(c):
    assert ask(c, "hello").json()["status"] == "WELCOME"
    assert ask(c).json()["status"] == "ANSWERED"


def test_7_a_model_error_does_not_count(c, monkeypatch):
    def broken(*a):
        raise llm.ModelError("rate limit")
    monkeypatch.setattr(llm, "ask_model", broken)
    assert ask(c).json()["status"] == "ERROR"
    monkeypatch.setattr(llm, "ask_model", lambda q, p, *a: good_model(q, p))
    assert ask(c).json()["status"] == "ANSWERED"


@pytest.fixture
def example(c, monkeypatch):
    """One example question with its saved answer (app/demo.py, Edwin)."""
    from app import api, config, demo
    monkeypatch.setattr(config, "EXAMPLE_QUESTIONS", ["Is Chevron overruled?"])
    assert demo.make_all(api.STATE["searcher"], api.STATE["index"], log=lambda m: None) == 1
    return "Is Chevron overruled?"


def test_8_example_questions_never_count(c, example):
    assert ask(c, example).status_code == 200                       # before the free question
    assert ask(c).status_code == 200                                # the free question is still there
    assert ask(c, example).status_code == 200                       # and after it
    assert ask(c, "Another one?").status_code == 403


def test_9_a_logged_in_user_is_not_limited_by_this_rule(c):
    sign_up(c)
    assert ask(c).status_code == 200
    assert ask(c, "And what about his private acts?").status_code == 200


def test_10_an_admin_is_not_limited_by_this_rule(c, clean_db):
    clean_db.create_user("boss@example.com", PW)
    log_in(c, "boss@example.com")
    assert ask(c).status_code == 200
    assert ask(c, "And what about his private acts?").status_code == 200


def test_11_me_says_how_many_free_questions_are_left(c):
    assert c.get("/api/me").json()["free_questions_left"] == 1
    ask(c)
    assert c.get("/api/me").json()["free_questions_left"] == 0
    sign_up(c)
    assert c.get("/api/me").json()["free_questions_left"] is None  # an account: this rule does not apply
