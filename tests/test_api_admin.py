"""The admin JSON API (step 5.9). Roles are checked on the server for EVERY route (SR35, NFR8).
Uses the TEST database; no search index and no model."""
import pytest
from fastapi.testclient import TestClient

PW = "a-long-password"


@pytest.fixture
def c(clean_db, monkeypatch):
    from app import api, main
    monkeypatch.setattr(main, "load_index", lambda: None)
    api.FAILED_BY_IP.clear()
    clean_db.create_user("boss@example.com", PW)                      # admin
    clean_db.create_user("reader@example.com", PW, role="user")
    with TestClient(main.app) as client:
        yield client


def csrf(c):
    return {"X-CSRF-Token": c.get("/api/me").json()["csrf"]}


def log_in(c, email):
    assert c.post("/api/login", json={"email": email, "password": PW}, headers=csrf(c)).status_code == 200


def admin_routes():
    """Every route of the admin API, read from the app itself (its OpenAPI description, which lists
    every route of every included router), so a new route cannot be forgotten here."""
    from app.main import app
    out = []
    for path, methods in app.openapi()["paths"].items():
        if path.startswith("/api/admin"):
            url = path.replace("{run_id}", "1").replace("{qid}", "A001").replace("{log_id}", "1") \
                      .replace("{user_id}", "1")
            out += [(m.upper(), url) for m in methods if m in ("get", "post")]
    return out


def call(c, method, url, headers=None):
    return c.get(url) if method == "GET" else c.post(url, json={}, headers=headers or {})


def test_there_are_admin_routes():
    assert len(admin_routes()) >= 18


def test_every_admin_route_refuses_visitors(c, clean_db):                     # SR35
    for method, url in admin_routes():
        assert call(c, method, url, csrf(c)).status_code == 401, (method, url)
    with clean_db.connect() as con:
        assert con.execute("SELECT count(*) AS n FROM users").fetchone()["n"] == 2       # nothing created


def test_every_admin_route_refuses_users(c, clean_db):                        # SR35, NFR8
    log_in(c, "reader@example.com")
    for method, url in admin_routes():
        assert call(c, method, url, csrf(c)).status_code == 403, (method, url)
    with clean_db.connect() as con:
        assert con.execute("SELECT count(*) AS n FROM jobs").fetchone()["n"] == 0        # nothing started


def test_every_admin_post_needs_the_csrf_token(c):
    log_in(c, "boss@example.com")
    for method, url in admin_routes():
        if method == "POST":
            assert call(c, method, url).status_code == 403, url


def test_admin_opens_every_page_on_an_empty_database(c):
    log_in(c, "boss@example.com")
    for url in ["/api/admin/home", "/api/admin/settings", "/api/admin/eval", "/api/admin/questions",
                "/api/admin/questions/export", "/api/admin/abstentions", "/api/admin/analytics",
                "/api/admin/corpus", "/api/admin/users"]:
        assert c.get(url).status_code == 200, url
    assert c.get("/api/admin/eval/1").status_code == 404                  # no such run
    assert c.get("/api/admin/settings/preview",
                 params={"tau_abstain": 0.5, "tau_confident": 0.6, "min_retrieval": 0.3}).status_code == 404


def test_settings_are_saved_within_limits(c):
    log_in(c, "boss@example.com")
    body = {"tau_abstain": 0.6, "tau_confident": 0.4, "min_retrieval": 0.3, "top_k": 99, "retrieve_k": 2,
            "use_reranker": True}
    s = c.post("/api/admin/settings", json=body, headers=csrf(c)).json()
    assert s["tau_confident"] == 0.6                 # never below the abstention threshold
    assert s["top_k"] == 10 and s["retrieve_k"] == 8 and s["use_reranker"] is True
    assert c.get("/api/admin/settings").json()["tau_abstain"] == 0.6


Q = {"id": "J001", "tag": "unanswerable", "split": "tune", "question": "Can I sue my neighbour?",
     "why": "personal legal advice", "author": "Joe"}


def test_add_change_and_export_a_test_question(c):                           # FR13a-c
    log_in(c, "boss@example.com")
    assert c.post("/api/admin/questions", json=Q, headers=csrf(c)).json()["question"] == Q["question"]
    c.post("/api/admin/questions", json={**Q, "split": "test"}, headers=csrf(c))      # change it
    [q] = c.get("/api/admin/questions", params={"tag": "unanswerable"}).json()
    assert q["id"] == "J001" and q["split"] == "test"
    assert '"id": "J001"' in c.get("/api/admin/questions/export").text
    assert c.get("/api/admin/questions", params={"tag": "answerable"}).json() == []


def test_bad_test_question_is_refused(c, clean_db):
    log_in(c, "boss@example.com")
    for bad in [{**Q, "tag": "maybe"}, {**Q, "split": "train"}, {**Q, "id": " "}]:
        assert c.post("/api/admin/questions", json=bad, headers=csrf(c)).status_code == 400
    with clean_db.connect() as con:
        assert con.execute("SELECT count(*) AS n FROM test_questions").fetchone()["n"] == 0


def logged_question(clean_db, user_email="reader@example.com"):
    """One NOT_SUPPORTED question in the log, asked by the user."""
    with clean_db.connect() as con:
        uid = con.execute("SELECT id FROM users WHERE email = %s", (user_email,)).fetchone()["id"]
        return con.execute("""INSERT INTO query_log (question, status, reason, support_score, top_score, details, user_id)
                              VALUES ('Who won the 2030 election?', 'NOT_SUPPORTED', 'no passage is close enough',
                              0, 0.2, '{"passages": [], "removed": []}', %s) RETURNING id""", (uid,)).fetchone()["id"]


def test_abstentions_do_not_say_who_asked(c, clean_db):                      # FR22
    log_id = logged_question(clean_db)
    log_in(c, "boss@example.com")
    [row] = c.get("/api/admin/abstentions").json()
    assert row["id"] == log_id and row["question"] == "Who won the 2030 election?"
    assert "user_id" not in row and "reader@example.com" not in str(row)


def test_label_and_add_to_the_test_set(c, clean_db):                         # SR43
    log_id = logged_question(clean_db)
    log_in(c, "boss@example.com")
    r = c.post(f"/api/admin/abstentions/{log_id}/label", json={"label": "add as unanswerable test question"},
               headers=csrf(c)).json()
    assert r["prefill"] == {"question": "Who won the 2030 election?", "tag": "unanswerable"}
    assert c.get("/api/admin/abstentions").json()[0]["label"] == "add as unanswerable test question"
    assert c.post(f"/api/admin/abstentions/{log_id}/label", json={"label": "whatever"},
                  headers=csrf(c)).status_code == 400
    assert c.post("/api/admin/abstentions/99999/label", json={"label": "add as answerable test question"},
                  headers=csrf(c)).status_code == 404               # the Jinja route crashed here (500)
