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
    assert again["status"] == "NOT_SUPPORTED" and again["saved_at"] > first and len(demo.all_saved()) == 1


def test_a_failed_refresh_keeps_the_answer_already_saved(c, demo, monkeypatch):    # e.g. Groq's daily limit
    from app import api
    monkeypatch.setattr(llm, "ask_model", lambda q, p: (_ for _ in ()).throw(llm.ModelError("429 rate limit")))
    assert demo.make_all(api.STATE["searcher"], api.STATE["index"], log=lambda m: None) == 0
    assert demo.saved_answer(EXAMPLE)["status"] == "ANSWERED"


def test_a_saved_answer_goes_to_the_users_log_like_any_question(c, demo, clean_db):   # SPEC 11, the two logs
    c.post("/api/signup", json={"email": "reader@example.com", "password": "a-long-password"}, headers=csrf(c))
    shown = ask(c, EXAMPLE).json()
    with clean_db.connect() as con:
        row = con.execute("SELECT event, query_id, detail FROM user_log ORDER BY id DESC LIMIT 1").fetchone()
    assert row["event"] == "question" and row["query_id"] == shown["id"] and row["detail"]["status"] == "ANSWERED"


# --- Groq's per-minute limit while making the saved answers (Joe, 2026-11-21: make_all on Railway saved few answers) ---
LIMIT = "language model failed: rate limit reached, retry after 7 s"
DAY = "language model failed: rate limit reached per day, retry after 2400 s"


@pytest.fixture
def made(c, monkeypatch):
    """make_all with a pipeline that answers from a script of statuses, and a sleep that only records."""
    from app import api, config, demo
    monkeypatch.setattr(config, "EXAMPLE_QUESTIONS", [EXAMPLE, "Was Chevron overruled?"])
    real, slept = demo.answer, []
    monkeypatch.setattr(demo.time, "sleep", slept.append)

    def run(script):
        calls = iter(script)

        def fake(q, *a, **k):
            reason = next(calls)
            if reason is None:
                return real(q, *a, **k)
            return {"question": q, "status": "ERROR", "reason": reason, "shown_sentences": []}
        monkeypatch.setattr(demo, "answer", fake)
        return demo.make_all(api.STATE["searcher"], api.STATE["index"], log=lambda m: None), slept
    return run


def test_the_minute_limit_is_waited_for_and_the_same_question_asked_again(made):
    saved, slept = made([LIMIT, None, LIMIT, LIMIT, None])
    assert saved == 2 and slept == [8.0, 8.0, 8.0]                 # the wait Groq gives, plus one second


def test_the_daily_limit_stops_at_once_without_waiting(made):
    saved, slept = made([None, DAY])
    assert saved == 1 and slept == []                               # the first answer is kept, no 40-minute sleep


def test_another_error_is_not_retried(made):
    saved, slept = made(["language model failed: timeout", None])
    assert saved == 1 and slept == []


def test_the_retries_end(made):
    saved, slept = made([LIMIT] * 7 + [None])
    assert saved == 1 and len(slept) == 6                           # 6 waits, then the next question
