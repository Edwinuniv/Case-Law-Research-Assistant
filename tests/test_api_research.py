"""The research API behind the chat page (step 5.7): /api/ask, /api/passage, /api/history.
Fake search and fake model (like tests/test_pipeline.py); TEST database."""
import pytest
from fastapi.testclient import TestClient
from app import llm
from tests.test_citations import INDEX
from tests.test_verify import PASSAGE, QUOTE

PW = "a-long-password"
BEFORE = "Syllabus text. " * 10
OPINION = BEFORE + PASSAGE["text"] + " More text after the passage."
GOOD = "The President has absolute immunity for conclusive and preclusive actions."


class FakeSearcher:
    def search(self, q, k):
        return [{**PASSAGE, "opinion_label": "Majority opinion", "section": "Part I", "is_syllabus": False,
                 "date_filed": "2024-07-01"}]

    def choose(self, q, found, top_k, use_reranker):
        return found[:top_k]


def good_model(q, p):
    return {"status": "SUPPORTED", "sentences": [{"text": GOOD, "sources": ["P1"], "quote": QUOTE}]}


@pytest.fixture
def c(clean_db, monkeypatch):
    from app import api, main
    monkeypatch.setattr(main, "load_index", lambda: None)          # no real index in the tests
    api.FAILED_BY_IP.clear()
    with clean_db.connect() as con:                                 # one decision, opinion and passage
        con.execute("""INSERT INTO decisions (decision_id, all_cluster_ids, docket_number, case_name, date_filed,
                       citations, source_url, licence) VALUES (9987186, '{9987186}', '23-939',
                       'Trump v. United States', '2024-07-01', '{"603 U.S. 593"}',
                       'https://www.courtlistener.com/opinion/9987186/x/', 'Public Domain Mark 1.0')""")
        con.execute("INSERT INTO opinions (opinion_id, decision_id, label, text, licence) "
                    "VALUES (1, 9987186, 'Majority opinion', %s, 'Public Domain Mark 1.0')", (OPINION,))
        con.execute("INSERT INTO chunks (chunk_id, opinion_id, decision_id, section, is_syllabus, start_char, "
                    "end_char, text) VALUES ('1-0', 1, 9987186, 'Part I', FALSE, %s, %s, %s)",
                    (len(BEFORE), len(BEFORE) + len(PASSAGE["text"]), PASSAGE["text"]))
    clean_db.create_user("reader@example.com", PW, role="user")
    clean_db.create_user("other@example.com", PW, role="user")
    monkeypatch.setitem(api.STATE, "searcher", FakeSearcher())
    monkeypatch.setitem(api.STATE, "index", INDEX)
    monkeypatch.setattr(llm, "ask_model", good_model)
    with TestClient(main.app) as client:
        yield client


def csrf(c):
    return {"X-CSRF-Token": c.get("/api/me").json()["csrf"]}


def log_in(c, email="reader@example.com"):
    assert c.post("/api/login", json={"email": email, "password": PW}, headers=csrf(c)).status_code == 200


def ask(c, question="Is the President immune from prosecution?"):
    return c.post("/api/ask", json={"question": question}, headers=csrf(c))


def logged(clean_db):
    with clean_db.connect() as con:
        return con.execute("SELECT * FROM query_log ORDER BY id").fetchall()


def test_ask_needs_login(c, clean_db):                                          # SR33 (new)
    assert ask(c).status_code == 401
    assert logged(clean_db) == []


def test_ask_needs_the_csrf_token(c):
    log_in(c)
    assert c.post("/api/ask", json={"question": "Is the President immune?"}).status_code == 403


def test_question_length_is_checked(c, clean_db):                               # SR3
    log_in(c)
    for q in ["ab", "x" * 1001]:
        r = ask(c, q)
        assert r.status_code == 400 and "between 3 and 1,000 characters" in r.json()["detail"]
    assert logged(clean_db) == []                                    # the model was not called


def test_index_not_ready(c, monkeypatch):
    from app import api
    monkeypatch.setitem(api.STATE, "searcher", None)
    log_in(c)
    assert ask(c).status_code == 503


def test_verified_answer_with_citation_from_our_database(c):                    # SR21, SR31, FR5
    log_in(c)
    r = ask(c).json()
    assert r["status"] == "ANSWERED"
    [s] = r["sentences"]
    assert s["text"] == GOOD
    [cite] = s["citations"]
    assert cite["chunk_id"] == "1-0" and cite["quote"] == QUOTE
    assert cite["label"] == "Trump v. United States, 603 U.S. 593 (2024) · Majority opinion"
    assert [p["chunk_id"] for p in r["passages"]] == ["1-0"] and r["passages"][0]["text"] == PASSAGE["text"]


def test_fabricated_citation_never_reaches_the_user(c, monkeypatch):            # FR7, SR28
    monkeypatch.setattr(llm, "ask_model", lambda q, p: {"status": "SUPPORTED", "sentences": [
        {"text": "See Fake v. Case, 999 U.S. 9999.", "sources": ["P1"], "quote": QUOTE}]})
    log_in(c)
    r = ask(c).json()
    assert r["status"] == "NOT_SUPPORTED" and r["sentences"] == [] and r["removed_count"] == 1
    assert "Fake v. Case" not in str(r)
    assert len(r["passages"]) == 1                                   # passages still shown (FR5)


def test_model_failure_shows_no_text(c, monkeypatch):
    def broken(q, p):
        raise llm.ModelError("timeout after 30 seconds")
    monkeypatch.setattr(llm, "ask_model", broken)
    log_in(c)
    r = ask(c).json()
    assert r["status"] == "ERROR" and r["sentences"] == []


def test_every_question_is_saved_with_who_asked(c, clean_db):                   # FR28
    log_in(c)
    r = ask(c).json()
    [row] = logged(clean_db)
    assert row["id"] == r["id"] and row["status"] == "ANSWERED" and row["user_id"] is not None


def test_each_question_is_answered_on_its_own(c, monkeypatch):
    """The chat must not pretend to remember: the model only gets the current question."""
    seen = []
    monkeypatch.setattr(llm, "ask_model", lambda q, p: seen.append(q) or good_model(q, p))
    log_in(c)
    ask(c, "Is the President immune from prosecution?")
    ask(c, "And what about his private acts?")
    assert seen == ["Is the President immune from prosecution?", "And what about his private acts?"]


def test_history_shows_only_my_questions(c):
    log_in(c, "other@example.com")
    other_id = ask(c, "A question from someone else").json()["id"]
    c.post("/api/logout", headers=csrf(c))
    log_in(c)
    mine = ask(c).json()
    h = c.get("/api/history").json()
    assert [x["id"] for x in h] == [mine["id"]] and h[0]["status"] == "ANSWERED"
    assert c.get(f"/api/history/{other_id}").status_code == 404      # not 403: we do not say it exists


def test_history_shows_the_same_answer_without_calling_the_model(c, monkeypatch):
    log_in(c)
    first = ask(c).json()
    calls = []
    monkeypatch.setattr(llm, "ask_model", lambda q, p: calls.append(q))
    again = c.get(f"/api/history/{first['id']}").json()
    assert again == first and calls == []


def test_history_needs_login(c):
    assert c.get("/api/history").status_code == 401
    assert c.get("/api/history/1").status_code == 401


def test_passage_panel_highlights_the_quote(c):                                  # SR31
    log_in(c)
    messy = "ENJOYS   absolute\nimmunity for actions within his conclusive"   # other spaces and capitals
    r = c.get("/api/passage/1-0", params={"quote": messy}).json()
    assert r["marked"].lower() == QUOTE.lower()
    assert r["inside_before"] + r["marked"] + r["inside_after"] == PASSAGE["text"]
    assert r["before"].endswith("Syllabus text. ") and r["after"].startswith(" More text")
    assert r["source_url"].startswith("https://www.courtlistener.com/") and r["citation"] == "603 U.S. 593"


def test_passage_without_quote_or_unknown(c):
    log_in(c)
    r = c.get("/api/passage/1-0").json()
    assert r["marked"] == "" and r["inside_before"] == PASSAGE["text"]
    assert c.get("/api/passage/no-such-chunk").status_code == 404


def test_passage_needs_login(c):
    assert c.get("/api/passage/1-0").status_code == 401
