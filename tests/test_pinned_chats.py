"""Pinned chats (SPEC 11, 2026-11-21), written from the rule before the code. TEST database, fake search and model."""
from tests.test_api_research import c, csrf   # noqa: F401  (c is the fixture)
from tests.test_chats import ask, reader, other   # noqa: F401  (fixtures)


def pin(c, chat, pinned=True):
    return c.post(f"/api/chats/{chat}/pin", json={"pinned": pinned}, headers=csrf(c))


def order(c):
    return [(x["title"], bool(x["pinned_at"])) for x in c.get("/api/chats").json()]


def new_chat(c, title):
    return ask(c, title).json()["chat_id"]


def test_a_pinned_chat_comes_first_and_the_others_keep_their_order(c, reader):
    a, b, d = new_chat(c, "Question A here"), new_chat(c, "Question B here"), new_chat(c, "Question D here")
    assert [t for t, _ in order(c)] == ["Question D here", "Question B here", "Question A here"]
    assert pin(c, a).status_code == 200
    assert order(c) == [("Question A here", True), ("Question D here", False), ("Question B here", False)]


def test_the_most_recently_pinned_is_on_top(c, reader):
    a, b = new_chat(c, "Question A here"), new_chat(c, "Question B here")
    pin(c, b)
    pin(c, a)
    assert [t for t, p in order(c) if p] == ["Question A here", "Question B here"]


def test_asking_in_a_pinned_chat_keeps_it_in_its_place(c, reader):
    a, b = new_chat(c, "Question A here"), new_chat(c, "Question B here")
    pin(c, b)
    pin(c, a)
    ask(c, "And another question?", b)                       # B has the newest activity, A was pinned last
    assert [t for t, p in order(c) if p] == ["Question A here", "Question B here"]


def test_unpinning_puts_it_back_among_the_others(c, reader):
    a, b = new_chat(c, "Question A here"), new_chat(c, "Question B here")
    pin(c, a)
    assert pin(c, a, False).status_code == 200
    assert order(c) == [("Question B here", False), ("Question A here", False)]


def test_only_the_accounts_own_chat_and_only_logged_in(c, reader, other):
    theirs = ask(other, "Their question here").json()["chat_id"]
    assert pin(c, theirs).status_code == 404 and pin(c, 999999).status_code == 404
    c.post("/api/logout", headers=csrf(c))
    assert pin(c, theirs).status_code == 401


def test_at_most_ten_pinned(c, reader, clean_db):
    # made in the database: 11 questions would pass a free account's 10 a day and the 10 a minute per address
    chats = [clean_db.create_chat(reader, f"Question number {n}") for n in range(11)]
    assert all(pin(c, x).status_code == 200 for x in chats[:10])
    assert pin(c, chats[10]).status_code == 409
    assert pin(c, chats[0]).status_code == 200              # pinning one already pinned is not an 11th
