"""Page previews for administrators (SPEC 11, 2026-11-20), written from the rule before the code. TEST database."""
import pytest
from tests.test_api_research import c as research_client, csrf   # noqa: F401  (the fixture is used below)
from tests.test_visitor_accounts import sign_up, log_in, PW


@pytest.fixture
def c(research_client):
    from app import api
    api.SIGNUPS_BY_IP.clear()
    return research_client


@pytest.mark.parametrize("code, title", [("401", "Please log in"), ("403", "Administrators only")])
def test_an_administrator_sees_the_servers_own_refusal_pages(c, clean_db, code, title):
    clean_db.create_user("boss@example.com", PW)
    log_in(c, "boss@example.com")
    r = c.get(f"/admin-preview/{code}")
    assert r.status_code == 200 and title in r.text and "<html" in r.text   # 200: a preview, not a refusal


def test_nobody_else_sees_them(c, clean_db):
    assert c.get("/admin-preview/401").status_code == 401           # a visitor: the real refusal
    sign_up(c, "reader@example.com")
    assert c.get("/admin-preview/403").status_code == 403           # a user account: the real refusal


def test_an_unknown_code_is_not_found(c, clean_db):
    clean_db.create_user("boss@example.com", PW)
    log_in(c, "boss@example.com")
    assert c.get("/admin-preview/500").status_code == 404
