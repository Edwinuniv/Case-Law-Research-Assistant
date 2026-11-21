"""Edit and versions in a chat (SPEC 11, 2026-11-21), written from the rule before the code: every question can have
a parent (the answer it followed); an edit is a new question with the same parent as the one edited. TEST database,
fake search and model from tests/test_api_research.py."""
import pytest
from app import api, llm
from app.pipeline import answer as real_answer
from tests.test_api_research import c, csrf, logged   # noqa: F401  (c is the fixture)
from tests.test_chats import reader, other, FIRST, SECOND   # noqa: F401  (fixtures)


def ask(c, question, chat_id=None, **parent):
    """parent_id=... sends the parent (None: the first place of the chat); no keyword: no parent sent at all."""
    body = {"question": question, **({"chat_id": chat_id} if chat_id is not None else {}), **parent}
    return c.post("/api/ask", json=body, headers=csrf(c))


def turns(c, chat):
    return {t["question"]: t for t in c.get(f"/api/chats/{chat}").json()["turns"]}


def test_the_parent_is_saved_and_given_back_with_the_chat(c, reader):
    first = ask(c, FIRST, parent_id=None).json()
    second = ask(c, SECOND, first["chat_id"], parent_id=first["id"]).json()
    t = turns(c, first["chat_id"])
    assert t[FIRST]["linked"] is True and t[FIRST]["parent"] is None
    assert t[SECOND]["linked"] is True and t[SECOND]["parent"] == first["id"] and second["parent"] == first["id"]


def test_an_edit_is_a_new_question_beside_the_old_one_and_nothing_is_deleted(c, reader, clean_db):
    first = ask(c, FIRST, parent_id=None).json()
    chat = first["chat_id"]
    ask(c, SECOND, chat, parent_id=first["id"])
    edited = ask(c, "And his unofficial acts?", chat, parent_id=first["id"]).json()     # SECOND, edited
    t = turns(c, chat)
    assert t[SECOND]["parent"] == t["And his unofficial acts?"]["parent"] == first["id"]
    assert edited["status"] == "ANSWERED" and len(logged(clean_db)) == 3


def test_editing_the_first_question_makes_a_second_first_question(c, reader):
    first = ask(c, FIRST, parent_id=None).json()
    ask(c, "Is the President immune from criminal prosecution?", first["chat_id"], parent_id=None)
    assert {t["parent"] for t in turns(c, first["chat_id"]).values()} == {None}


def test_a_parent_from_another_chat_or_unknown_is_refused_before_the_model(c, reader, monkeypatch):
    mine = ask(c, FIRST, parent_id=None).json()
    elsewhere = ask(c, SECOND, parent_id=None).json()                                   # another chat of mine
    monkeypatch.setattr(llm, "ask_model", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no model call")))
    assert ask(c, "x question here", mine["chat_id"], parent_id=elsewhere["id"]).status_code == 404
    assert ask(c, "x question here", mine["chat_id"], parent_id=999999).status_code == 404


def test_a_parent_needs_a_chat(c, reader):
    first = ask(c, FIRST, parent_id=None).json()
    assert ask(c, SECOND, parent_id=first["id"]).status_code == 400                     # no chat_id: no tree


def test_a_question_sent_without_a_parent_is_read_as_before(c, reader):
    first = ask(c, FIRST).json()                                                        # an older page, no parent
    ask(c, SECOND, first["chat_id"])
    assert {t["linked"] for t in turns(c, first["chat_id"]).values()} == {False}


def test_a_passage_request_uses_the_parents_answer_not_the_newest(c, reader, clean_db, monkeypatch):
    clean_db.set_setting("passage_summaries", True)
    first = ask(c, FIRST, parent_id=None).json()
    chat = first["chat_id"]
    newest = ask(c, SECOND, chat, parent_id=first["id"]).json()
    seen = []

    def spy(question, searcher, index, settings, skip_gate=False, history=None, previous=None):
        seen.append(previous)
        return real_answer(question, searcher, index, settings, previous=previous)
    monkeypatch.setattr(api, "answer", spy)
    ask(c, "summarize the first passage", chat, parent_id=first["id"])                  # a version under FIRST
    ask(c, "summarize the first passage", chat, parent_id=newest["id"])
    assert seen[0]["question"] == FIRST and seen[1]["question"] == SECOND
