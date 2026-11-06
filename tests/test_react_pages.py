"""FastAPI serves the React app at / (step 5.8, moved from /app in step 5.10). Uses the TEST database."""
from fastapi.testclient import TestClient

from app import config


def client(monkeypatch, dist):
    from app import main
    monkeypatch.setattr(main, "load_index", lambda: None)
    monkeypatch.setattr(main, "FRONTEND", dist)
    return TestClient(main.app)


def test_every_page_is_the_react_page(clean_db, monkeypatch, tmp_path):
    (tmp_path / "index.html").write_text("<div id=root></div>")
    with client(monkeypatch, tmp_path) as c:
        for url in ["/", "/login", "/some/page"]:                       # React Router picks the page
            r = c.get(url)
            assert r.status_code == 200 and "<div id=root>" in r.text, url


def test_clear_message_when_not_built(clean_db, monkeypatch, tmp_path):
    with client(monkeypatch, tmp_path / "missing") as c:
        r = c.get("/")
        assert r.status_code == 404 and "npm run build" in r.text


def test_api_and_health_are_not_the_react_page(clean_db, monkeypatch, tmp_path):
    """The React page answers every address, so /api and /health must be found before it."""
    (tmp_path / "index.html").write_text("<div id=root></div>")
    with client(monkeypatch, tmp_path) as c:
        assert c.get("/health").json()["ok"] is True
        assert "csrf" in c.get("/api/me").json()
        r = c.get("/api/no-such-route")                                  # JSON 404, not the page
        assert r.status_code == 404 and r.json() == {"detail": "Not Found"}


def test_the_jinja_pages_are_gone(clean_db, monkeypatch, tmp_path):
    """Step 5.10: the old forms that wrote without a CSRF token no longer exist."""
    with client(monkeypatch, tmp_path) as c:
        assert c.post("/ask", data={"question": "Is the President immune?"}).status_code == 405
        assert c.post("/admin/login", data={"email": "a@b.c", "password": "x"}).status_code == 405
        assert c.post("/admin/users", data={"email": "a@b.c", "password": "a-long-password"}).status_code == 405
    with clean_db.connect() as con:
        assert con.execute("SELECT count(*) AS n FROM users").fetchone()["n"] == 0


def test_disclaimer_on_every_page():                                     # SR7
    """The footer is in index.html itself (outside React), so every page and the built copy carry it."""
    html = (config.ROOT / "frontend" / "index.html").read_text()
    assert "research aid, not legal advice" in html
