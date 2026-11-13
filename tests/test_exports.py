"""PDF exports (SPEC section 11, 2026-11-13; part 4 of docs/PLAN_2026-11-13.md): written from the rule in SPEC.
The text of each PDF is read back with pypdf. Fake search and model; TEST database."""
import io

import pytest
from pypdf import PdfReader
from tests.test_api_research import c as research_client, csrf, ask   # noqa: F401  (the fixture is used below)

PW = "a-long-password"


@pytest.fixture
def c(research_client, clean_db):
    from app import api
    api.SIGNUPS_BY_IP.clear()
    api.FAILED_BY_IP.clear()
    clean_db.create_user("boss@example.com", PW)                      # an administrator
    return research_client


def post(c, path, body=None):
    return c.post(path, json=body or {}, headers=csrf(c))


def text_of(response):
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf" and "attachment" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")
    text = " ".join(page.extract_text() for page in PdfReader(io.BytesIO(response.content)).pages)
    return " ".join(text.split())                                      # table cells come back on separate lines


def a_reader_with_history(c):
    """reader@example.com: signed up, 2 questions, logged out, logged in again."""
    post(c, "/api/signup", {"email": "reader@example.com", "password": PW})
    ask(c, "Is the President immune from prosecution?")
    ask(c, "What did the Court say about official acts?")
    post(c, "/api/logout")
    post(c, "/api/login", {"email": "reader@example.com", "password": PW})
    post(c, "/api/logout")


def test_one_users_pdf_has_details_log_and_questions(c, clean_db):          # rule 1
    a_reader_with_history(c)
    uid = clean_db.check_login("reader@example.com", PW)[0]["id"]
    post(c, "/api/login", {"email": "boss@example.com", "password": PW})
    t = text_of(c.get(f"/api/admin/users/{uid}/pdf"))
    assert "reader@example.com" in t and "made" in t and "boss@example.com" in t           # rule 4: when, by whom
    assert "Number of logins 1" in t and "Questions asked 2" in t
    for event in ("signup", "question", "logout", "login"):
        assert event in t
    assert "Is the President immune from prosecution?" in t and "What did the Court say about official acts?" in t
    assert PW not in t                                                                      # rule 5


def test_the_list_has_one_row_per_account(c, clean_db):                    # rule 2
    a_reader_with_history(c)
    clean_db.create_visitor("quiet@example.com", PW)                   # never logged in, no question
    post(c, "/api/login", {"email": "boss@example.com", "password": PW})
    t = text_of(c.get("/api/admin/users/pdf"))
    assert "All accounts (3)" in t
    for email in ("boss@example.com", "reader@example.com", "quiet@example.com"):
        assert email in t
    assert "never" in t                                                 # quiet's last login


def test_only_admins_download_and_each_download_is_logged(c, clean_db):     # rule 3
    uid = clean_db.create_visitor("reader@example.com", PW)
    assert c.get("/api/admin/users/pdf").status_code == 401
    post(c, "/api/login", {"email": "reader@example.com", "password": PW})
    assert c.get("/api/admin/users/pdf").status_code == 403
    assert c.get(f"/api/admin/users/{uid}/pdf").status_code == 403
    post(c, "/api/logout")
    post(c, "/api/login", {"email": "boss@example.com", "password": PW})
    text_of(c.get(f"/api/admin/users/{uid}/pdf"))
    assert c.get("/api/admin/users/99999/pdf").status_code == 404
    with clean_db.connect() as con:
        rows = con.execute("SELECT action, target_user_id FROM admin_log WHERE action LIKE '%/pdf' ORDER BY id").fetchall()
    assert [(r["action"], r["target_user_id"]) for r in rows] == [(f"GET /api/admin/users/{uid}/pdf", uid),
                                                                   ("GET /api/admin/users/99999/pdf", None)]
    with clean_db.connect() as con:                                     # the missing account is kept in the detail
        assert con.execute("SELECT detail FROM admin_log WHERE action LIKE '%99999%'").fetchone()["detail"] == \
            {"target_not_found": 99999}


def test_an_administrators_pdf_shows_their_admin_log(c, clean_db):          # rule 1 (admins act in the admin log)
    post(c, "/api/login", {"email": "boss@example.com", "password": PW})
    boss = clean_db.check_login("boss@example.com", PW)[0]["id"]
    t = text_of(c.get(f"/api/admin/users/{boss}/pdf"))
    assert "Admin log" in t and "login" in t and "Number of logins 1" in t
