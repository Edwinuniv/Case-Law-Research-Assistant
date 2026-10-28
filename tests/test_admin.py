"""Login, roles, lock-out (SR33-SR36). Uses the TEST database."""
from fastapi.testclient import TestClient

def client():
    from app.main import app
    return TestClient(app)

def test_public_page_needs_no_login(clean_db):
    with client() as c:
        r = c.get("/")
        assert r.status_code == 200 and "research aid, not legal advice" in r.text            # SR7

def test_admin_pages_refuse_visitors(clean_db):                                       # SR35
    with client() as c:
        for url in ["/admin", "/admin/eval", "/admin/settings", "/admin/users", "/admin/questions"]:
            assert c.get(url).status_code == 401

def test_admin_can_log_in(clean_db):
    clean_db.create_user("boss@example.com", "a-long-password")
    with client() as c:
        c.post("/admin/login", data={"email": "boss@example.com", "password": "a-long-password"})
        assert c.get("/admin").status_code == 200

def test_lock_after_five_failures(clean_db):                                          # SR36
    clean_db.create_user("boss@example.com", "a-long-password")
    with client() as c:
        for _ in range(5):
            c.post("/admin/login", data={"email": "boss@example.com", "password": "wrong"})
        r = c.post("/admin/login", data={"email": "boss@example.com", "password": "a-long-password"})
        assert r.status_code == 401 and "locked" in r.text

def test_disabled_account_loses_access(clean_db):
    clean_db.create_user("boss@example.com", "a-long-password")
    with client() as c:
        c.post("/admin/login", data={"email": "boss@example.com", "password": "a-long-password"})
        with clean_db.connect() as con:
            con.execute("UPDATE users SET active = FALSE")
        assert c.get("/admin").status_code == 403

def test_passwords_are_hashed(clean_db):                                              # SR34
    clean_db.create_user("boss@example.com", "a-long-password")
    with clean_db.connect() as con:
        h = con.execute("SELECT password_hash FROM users").fetchone()["password_hash"]
    assert h.startswith("$2") and "a-long-password" not in h
