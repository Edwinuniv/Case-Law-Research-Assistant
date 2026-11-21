"""Passage summaries on the website (SPEC 11, 2026-11-21), written before the change to app/api.py (Joe's file, told):
in a chat, a passage request gets the chat's last answer; a visitor or a first message gets our fixed text. TEST database,
fake search and model from tests/test_api_research.py."""
import pytest
from app import api, llm
from tests.test_api_research import c, csrf, good_model   # noqa: F401  (c is the fixture)
from tests.test_chats import ask, reader                   # noqa: F401  (reader is the fixture)

REQUEST = "summurize the first passage"                    # the live message


@pytest.fixture(autouse=True)
def judge_says_yes(monkeypatch):
    """No test calls the real judge (Groq): it says "yes" unless a test sets another verdict (meaning check, 2026-11-21)."""
    monkeypatch.setattr(llm, "judge_summary", lambda statement, passage_text: "yes", raising=False)


@pytest.fixture
def model(monkeypatch):
    """The fake model of the website tests, recording the passages it received."""
    got = []

    def fake(question, passages, *a, **k):
        got.append(sorted(passages))
        return good_model(question, passages)
    monkeypatch.setattr(llm, "ask_model", fake)
    return got


def no_more_search(monkeypatch):
    monkeypatch.setattr(api.STATE["searcher"], "search", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no search")))


def test_in_a_chat_the_request_uses_the_last_answers_passages_without_a_search(c, reader, clean_db, model, monkeypatch):
    clean_db.set_setting("passage_summaries", True)
    chat = ask(c).json()["chat_id"]
    no_more_search(monkeypatch)
    r = ask(c, REQUEST, chat).json()
    assert r["status"] == "ANSWERED" and r["sentences"] and model == [["P1"], ["P1"]]


def test_switched_off_the_request_gets_the_fixed_text_and_no_model(c, reader, model, monkeypatch):
    chat = ask(c).json()["chat_id"]
    no_more_search(monkeypatch)
    r = ask(c, REQUEST, chat).json()
    assert r["status"] == "WELCOME" and len(model) == 1


def test_a_visitor_gets_the_fixed_text_and_keeps_the_free_question(c, clean_db, model, monkeypatch):
    clean_db.set_setting("passage_summaries", True)
    no_more_search(monkeypatch)
    r = ask(c, REQUEST).json()
    assert r["status"] == "WELCOME" and model == []
    assert c.get("/api/me").json()["free_questions_left"] == 1
