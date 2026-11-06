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
    clean_db.create_user("second@example.com", PW)                    # another admin
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


def test_every_admin_route_refuses_a_disabled_account(c, clean_db):           # SR35, NFR8
    """An administrator disabled while logged in loses every admin route at once (403):
    the account is read from the database at each request, not from the cookie."""
    for method, url in admin_routes():
        with clean_db.connect() as con:
            con.execute("UPDATE users SET active = TRUE WHERE email = 'second@example.com'")
        log_in(c, "second@example.com")
        token = csrf(c)                         # before disabling: /api/me ends a disabled account's session
        with clean_db.connect() as con:
            con.execute("UPDATE users SET active = FALSE WHERE email = 'second@example.com'")
        assert call(c, method, url, token).status_code == 403, (method, url)
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


def logged_question(clean_db):
    """One NOT_SUPPORTED question in the log, asked by a visitor (no account)."""
    with clean_db.connect() as con:
        return con.execute("""INSERT INTO query_log (question, status, reason, support_score, top_score, details)
                              VALUES ('Who won the 2030 election?', 'NOT_SUPPORTED', 'no passage is close enough',
                              0, 0.2, '{"passages": [], "removed": []}') RETURNING id""").fetchone()["id"]


def test_abstentions_do_not_say_who_asked(c, clean_db):                      # FR22
    log_id = logged_question(clean_db)
    log_in(c, "boss@example.com")
    [row] = c.get("/api/admin/abstentions").json()
    assert row["id"] == log_id and row["question"] == "Who won the 2030 election?"
    assert "user_id" not in row


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


def test_admin_creates_another_admin_who_can_then_log_in(c):                 # FR12
    log_in(c, "boss@example.com")
    accounts = c.post("/api/admin/users", json={"email": "new@example.com", "password": PW},
                      headers=csrf(c)).json()
    assert {"email": "new@example.com", "role": "admin"}.items() <= next(
        a for a in accounts if a["email"] == "new@example.com").items()
    assert all("password_hash" not in a for a in accounts)
    c.post("/api/logout", headers=csrf(c))
    log_in(c, "new@example.com")
    assert c.get("/api/me").json()["user"]["role"] == "admin"


def test_accounts_page_cannot_create_a_user_account(c, clean_db):            # SR33
    """SR33: the visitor has no account, so the accounts page only makes administrators."""
    log_in(c, "boss@example.com")
    r = c.post("/api/admin/users", json={"email": "reader@example.com", "password": PW, "role": "user"},
               headers=csrf(c))
    assert r.status_code == 400
    with clean_db.connect() as con:
        assert con.execute("SELECT count(*) AS n FROM users WHERE email = 'reader@example.com'").fetchone()["n"] == 0


def test_bad_new_accounts_are_refused(c, clean_db):
    log_in(c, "boss@example.com")
    for bad in [{"email": "x@example.com", "password": "short"},
                {"email": "not-an-email", "password": PW},
                {"email": "x@example.com", "password": PW, "role": "superuser"}]:
        assert c.post("/api/admin/users", json=bad, headers=csrf(c)).status_code == 400
    with clean_db.connect() as con:
        assert con.execute("SELECT count(*) AS n FROM users").fetchone()["n"] == 2


def test_disable_an_account_but_not_yourself(c, clean_db):
    with clean_db.connect() as con:
        ids = {r["email"]: r["id"] for r in con.execute("SELECT id, email FROM users").fetchall()}
    log_in(c, "boss@example.com")
    assert c.post(f"/api/admin/users/{ids['boss@example.com']}/toggle", headers=csrf(c)).status_code == 400
    assert c.post(f"/api/admin/users/{ids['second@example.com']}/toggle", headers=csrf(c)).status_code == 200
    assert c.post("/api/admin/users/99999/toggle", headers=csrf(c)).status_code == 404
    c.post("/api/logout", headers=csrf(c))
    r = c.post("/api/login", json={"email": "second@example.com", "password": PW}, headers=csrf(c))
    assert r.status_code == 401                                         # the disabled account cannot log in


def test_react_admin_pages_are_refused_by_the_server(c, clean_db, monkeypatch, tmp_path):   # SR35
    from app import main
    (tmp_path / "index.html").write_text("<div id=root></div>")
    monkeypatch.setattr(main, "FRONTEND", tmp_path)
    for url in ["/admin", "/admin/users", "/ADMIN", "http://testserver//admin/eval", "/admin/"]:
        assert c.get(url).status_code == 401, url
    assert c.get("/").status_code == 200                                # the research page is for everyone
    log_in(c, "second@example.com")
    with clean_db.connect() as con:                                     # disabled while logged in
        con.execute("UPDATE users SET active = FALSE WHERE email = 'second@example.com'")
    assert c.get("/admin").status_code == 403
    log_in(c, "boss@example.com")
    assert c.get("/admin/users").status_code == 200 and c.get("/Admin/settings").status_code == 200
