"""Limit of questions per IP address on /api/ask (step 5.12).
Why: since step 5.11 the research page is open to visitors (SR33), so anyone could send questions in a loop
and use up our model credit (Groq). Expected behaviour, written before the code:
- one address may ask at most 10 questions per minute; the 11th gets HTTP 429 with a clear message,
  and the model is NOT called and nothing is saved;
- the limit is per address: another visitor can still ask;
- after a minute the address may ask again;
- a question refused by SR3 (too short or too long) does not call the model, so it does not count.
Same fake search, fake model and TEST database as tests/test_api_research.py."""
import time
from fastapi.testclient import TestClient
from app import llm
from tests.test_api_research import c, ask, good_model, logged   # noqa: F401 (c is the fixture)


def count_model_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "ask_model", lambda q, p: calls.append(q) or good_model(q, p))
    return calls


def test_eleventh_question_in_a_minute_is_refused(c, clean_db, monkeypatch):
    calls = count_model_calls(monkeypatch)
    for i in range(10):
        assert ask(c, f"Question number {i}").status_code == 200
    r = ask(c, "One question too many")
    assert r.status_code == 429
    message = r.json()["detail"]
    assert "10 questions per minute" in message and "seconds" in message     # says what the limit is and how long to wait
    assert 1 <= int(r.headers["Retry-After"]) <= 60
    assert len(calls) == 10                     # the model was not called for the 11th
    assert len(logged(clean_db)) == 10          # and it was not saved as a question


def test_limit_is_per_address(c):
    from app import main
    for i in range(10):
        ask(c, f"Question number {i}")
    assert ask(c, "One question too many").status_code == 429
    with TestClient(main.app, client=("203.0.113.5", 50000)) as other:     # another visitor, another address
        assert ask(other, "Is the President immune from prosecution?").status_code == 200


def test_address_may_ask_again_after_a_minute(c, monkeypatch):
    now = [time.time()]
    monkeypatch.setattr(time, "time", lambda: now[0])
    for i in range(10):
        ask(c, f"Question number {i}")
    assert ask(c, "Too soon").status_code == 429
    now[0] += 61
    assert ask(c, "A minute later").status_code == 200


def test_refused_input_does_not_use_up_the_limit(c):                          # SR3 is checked first
    for _ in range(12):
        assert ask(c, "ab").status_code == 400
    assert ask(c, "Is the President immune from prosecution?").status_code == 200
