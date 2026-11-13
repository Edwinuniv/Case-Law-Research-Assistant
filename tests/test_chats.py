"""Saved chats for logged-in accounts, follow-ups connected behind the follow_ups setting (SPEC section 11, 2026-11-14).
Written from the rule in SPEC and the test table Joe approved, before the code.
Fake search and fake model from tests/test_api_research.py; TEST database.
The follow-up itself (what the model reads, the search in the chat's case) is Edwin's pipeline and is tested in
tests/test_pipeline.py; here we check only what the website gives it: the right history, or none."""
import pytest
from fastapi.testclient import TestClient
from app import api, llm, logs
from app.pipeline import answer as real_answer
from tests.test_api_research import c, csrf, logged, good_model, GOOD, QUOTE   # noqa: F401  (c is the fixture)
from tests.test_visitor_accounts import sign_up, log_in, PW

FIRST = "Is the President immune from prosecution?"
SECOND = "And what about his private acts?"


def ask(c, question=FIRST, chat_id=None):
    body = {"question": question} if chat_id is None else {"question": question, "chat_id": chat_id}
    return c.post("/api/ask", json=body, headers=csrf(c))


@pytest.fixture
def reader(c, clean_db):
    api.SIGNUPS_BY_IP.clear()
    sign_up(c, "reader@example.com")
    with clean_db.connect() as con:
        return con.execute("SELECT id FROM users WHERE email = 'reader@example.com'").fetchone()["id"]


@pytest.fixture
def other(c, clean_db):
    """Another account in another browser."""
    from app import main
    with TestClient(main.app, client=("203.0.113.7", 50000)) as o:
        sign_up(o, "other@example.com")
        yield o


@pytest.fixture
def histories(monkeypatch):
    """What the website gives pipeline.answer as history, one entry per question (None = no history).
    The question is then answered without history by the real pipeline (the fake search has no decision filter)."""
    seen = []

    def spy(question, searcher, index, settings, skip_gate=False, history=None):
        seen.append(history)
        return real_answer(question, searcher, index, settings)
    monkeypatch.setattr(api, "answer", spy)
    return seen


def follow_ups(clean_db, on):
    clean_db.set_setting("follow_ups", on)


def test_1_a_question_without_chat_id_starts_a_new_chat(c, reader, clean_db):
    r = ask(c).json()
    assert isinstance(r["chat_id"], int)
    with clean_db.connect() as con:
        chat = con.execute("SELECT * FROM chats WHERE id = %s", (r["chat_id"],)).fetchone()
    assert chat["user_id"] == reader and chat["title"] == FIRST
    assert ask(c, SECOND).json()["chat_id"] != r["chat_id"]          # no chat_id again: another new chat


def test_2_a_question_with_chat_id_is_added_to_that_chat(c, reader, clean_db):
    chat = ask(c).json()["chat_id"]
    assert ask(c, SECOND, chat).json()["chat_id"] == chat
    assert [row["chat_id"] for row in logged(clean_db)] == [chat, chat]


def test_3_someone_elses_chat_or_an_unknown_chat_is_404_before_the_model(c, reader, other, monkeypatch):
    theirs = ask(other).json()["chat_id"]
    calls = []
    monkeypatch.setattr(llm, "ask_model", lambda q, p, *a: calls.append(q) or good_model(q, p))
    assert ask(c, SECOND, theirs).status_code == 404
    assert ask(c, SECOND, 99999).status_code == 404
    assert calls == []


def test_4_a_visitor_cannot_send_a_chat_id(c):
    r = ask(c, FIRST, 1)
    assert r.status_code == 401 and "Log in to keep a chat" in r.json()["detail"]


def test_5_a_visitors_question_makes_no_chat(c, clean_db):
    r = ask(c).json()
    assert r["status"] == "ANSWERED" and r["chat_id"] is None
    with clean_db.connect() as con:
        assert con.execute("SELECT count(*) AS n FROM chats").fetchone()["n"] == 0


def test_6_follow_ups_off_by_default_no_history(c, reader, histories):
    chat = ask(c).json()["chat_id"]
    ask(c, SECOND, chat)
    assert histories == [None, None]                                 # each question answered on its own


def test_7_follow_ups_on_the_earlier_turn_with_only_verified_sentences(c, reader, clean_db, histories, monkeypatch):
    follow_ups(clean_db, True)
    monkeypatch.setattr(llm, "ask_model", lambda q, p, *a: {"status": "SUPPORTED", "sentences": [
        {"text": GOOD, "sources": ["P1"], "quote": QUOTE},
        {"text": "See Fake v. Case, 999 U.S. 9999.", "sources": ["P1"], "quote": QUOTE}]})    # removed by the verifier
    chat = ask(c).json()["chat_id"]
    ask(c, SECOND, chat)
    assert histories[0] is None                                      # the first question of a chat: no history
    [turn] = histories[1]
    assert turn["question"] == FIRST
    assert [s["text"] for s in turn["sentences"]] == [GOOD]          # the removed sentence is never sent back
    assert turn["sentences"][0]["quote"] == QUOTE and turn["sentences"][0]["sources"] == ["P1"]
    assert [(pid, p["chunk_id"]) for pid, p in turn["passages"]] == [("P1", "1-0")]


@pytest.mark.parametrize("first", ["hello", "error"])
def test_8_greetings_and_errors_are_not_in_the_history(c, reader, clean_db, histories, monkeypatch, first):
    follow_ups(clean_db, True)
    if first == "error":
        def broken(*a):
            raise llm.ModelError("rate limit")
        monkeypatch.setattr(llm, "ask_model", broken)
        chat = ask(c).json()["chat_id"]
        monkeypatch.setattr(llm, "ask_model", lambda q, p, *a: good_model(q, p))
    else:
        chat = ask(c, "hello").json()["chat_id"]
    ask(c, SECOND, chat)
    assert not histories[-1]                                         # nothing to continue


def test_9_follow_ups_on_a_new_chat_has_no_history(c, reader, clean_db, histories):
    follow_ups(clean_db, True)
    ask(c)
    ask(c, SECOND)                                                   # no chat_id: a new chat
    assert histories == [None, None]


def test_10_the_accounts_log_question_then_follow_up(c, reader):
    chat = ask(c).json()["chat_id"]
    second = ask(c, SECOND, chat).json()
    events = [(row["event"], row["detail"].get("chat_id"), row["query_id"]) for row in reversed(logs.user_log(reader))
              if row["event"] in ("question", "follow_up")]
    assert events[0][:2] == ("question", chat)
    assert events[1] == ("follow_up", chat, second["id"])


def test_11_list_of_my_chats(c, reader, other):
    ask(other)                                                       # someone else's chat
    old = ask(c).json()["chat_id"]
    ask(c, SECOND, old)
    new = ask(c, "Is Chevron overruled?").json()["chat_id"]
    chats = c.get("/api/chats").json()
    assert [(x["id"], x["title"], x["questions"]) for x in chats] == [(new, "Is Chevron overruled?", 1),
                                                                     (old, FIRST, 2)]
    from app import main
    with TestClient(main.app) as visitor:
        assert visitor.get("/api/chats").status_code == 401


def test_12_one_chat_with_its_answers_as_shown(c, reader, other):
    first = ask(c).json()
    second = ask(c, SECOND, first["chat_id"]).json()
    chat = c.get(f"/api/chats/{first['chat_id']}").json()
    assert chat["title"] == FIRST
    assert [(t["id"], t["question"]) for t in chat["turns"]] == [(first["id"], FIRST), (second["id"], SECOND)]
    assert chat["turns"][0]["shown"]["sentences"] == first["sentences"]
    theirs = ask(other).json()["chat_id"]
    assert c.get(f"/api/chats/{theirs}").status_code == 404


def test_13_an_administrator_switches_follow_ups(c, reader, clean_db):
    from app import main
    assert c.post("/api/admin/follow-ups", json={"on": True}, headers=csrf(c)).status_code == 403   # a 'user'
    clean_db.create_user("boss@example.com", PW)
    with TestClient(main.app, client=("203.0.113.9", 50000)) as admin:
        log_in(admin, "boss@example.com")
        assert admin.post("/api/admin/follow-ups", json={"on": True}, headers=csrf(admin)).status_code == 200
        assert clean_db.get_settings()["follow_ups"] is True
        assert admin.post("/api/admin/follow-ups", json={"on": False}, headers=csrf(admin)).status_code == 200
        assert clean_db.get_settings()["follow_ups"] is False


def test_14_questions_in_a_chat_count_toward_the_daily_limit(c, reader, clean_db):
    clean_db.set_setting("free_daily_questions", 2)
    chat = ask(c).json()["chat_id"]
    assert ask(c, SECOND, chat).status_code == 200
    assert ask(c, "A third one?", chat).status_code == 429
