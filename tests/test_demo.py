"""Demo answers saved in the database (2026-11-13, Dr. Salloum: show the jury without spending tokens or waiting).
Each example question of the chat page is answered ONCE by the real pipeline (with every check) and stored exactly as
the page shows it; /api/ask then returns the stored answer, with no search and no model call. Written before the code."""
import pytest
from app import llm
from tests.test_api_research import c, csrf, ask, logged, good_model        # the same test site: fake search and model

EXAMPLE = "Is the President immune from prosecution?"


@pytest.fixture
def demo(c, monkeypatch):
    from app import api, config, demo
    monkeypatch.setattr(config, "EXAMPLE_QUESTIONS", [EXAMPLE])
    assert demo.make_all(api.STATE["searcher"], api.STATE["index"], log=lambda m: None) == 1
    return demo


def test_an_example_question_is_answered_once_by_the_real_pipeline_and_stored_as_shown(demo, clean_db):
    saved = demo.saved_answer(EXAMPLE)
    assert saved["status"] == "ANSWERED" and saved["sentences"] and saved["passages"]      # with its citations
    assert saved["demo"] is True and saved["saved_at"]


def test_asking_an_example_question_returns_the_saved_answer_without_the_model(c, demo, monkeypatch):
    monkeypatch.setattr(llm, "ask_model", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no model call")))
    for text in [EXAMPLE, "  is the president immune from prosecution? ", "IS THE PRESIDENT IMMUNE FROM PROSECUTION"]:
        r = ask(c, text)
        assert r.status_code == 200 and r.json()["demo"] is True and r.json()["sentences"]


def test_another_question_still_goes_through_the_pipeline(c, demo):
    r = ask(c, "Is the President immune from civil suits?")
    assert r.status_code == 200 and not r.json().get("demo")


def test_a_saved_answer_is_logged_like_any_question(c, demo, clean_db):            # FR28: every question is logged
    ask(c, EXAMPLE)
    row = logged(clean_db)[-1]
    assert row["question"] == EXAMPLE and row["status"] == "ANSWERED" and "saved demo answer" in row["reason"]


def test_saved_answers_do_not_count_toward_the_limit_per_address(c, demo):          # no tokens are spent
    assert all(ask(c, EXAMPLE).status_code == 200 for _ in range(15))               # the limit is 10 a minute


def test_refreshing_replaces_the_saved_answers(c, demo, monkeypatch):
    from app import api
    first = demo.saved_answer(EXAMPLE)["saved_at"]
    monkeypatch.setattr(llm, "ask_model", lambda q, p: {"status": "NOT_SUPPORTED", "sentences": []})
    demo.make_all(api.STATE["searcher"], api.STATE["index"], log=lambda m: None)
    again = demo.saved_answer(EXAMPLE)
    assert again["status"] == "NOT_SUPPORTED" and again["saved_at"] >= first and len(demo.all_saved()) == 1
