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
