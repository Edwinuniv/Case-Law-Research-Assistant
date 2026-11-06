"""FastAPI serves the React app under /app (step 5.8). Uses the TEST database."""
from fastapi.testclient import TestClient


def client(monkeypatch, dist):
    from app import main
    monkeypatch.setattr(main, "load_index", lambda: None)
    monkeypatch.setattr(main, "FRONTEND", dist)
    return TestClient(main.app)


def test_every_app_page_is_the_react_page(clean_db, monkeypatch, tmp_path):
    (tmp_path / "index.html").write_text("<div id=root></div>")
    with client(monkeypatch, tmp_path) as c:
        for url in ["/app", "/app/", "/app/login", "/app/some/page"]:     # React Router picks the page
            r = c.get(url)
            assert r.status_code == 200 and "<div id=root>" in r.text, url


def test_clear_message_when_not_built(clean_db, monkeypatch, tmp_path):
    with client(monkeypatch, tmp_path / "missing") as c:
        r = c.get("/app")
        assert r.status_code == 404 and "npm run build" in r.text


def test_old_pages_still_work(clean_db, monkeypatch, tmp_path):
    """The Jinja pages stay until step 5.10, so the demo is never broken."""
    with client(monkeypatch, tmp_path) as c:
        assert c.get("/").status_code == 200
        assert c.get("/admin").status_code == 401
