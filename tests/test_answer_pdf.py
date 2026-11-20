"""An answer as a PDF (SPEC 11, 2026-11-20, from CedarPay's receipts), written from the rule before the code.
Fake search and model from tests/test_api_research.py; the PDF's text is read back with pypdf. TEST database."""
import io
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from tests.test_api_research import c as research_client, ask   # noqa: F401  (the fixture is used below)
from tests.test_visitor_accounts import sign_up


@pytest.fixture
def c(research_client):
    from app import api
    api.SIGNUPS_BY_IP.clear()
    return research_client


def pdf_text(r):
    return " ".join(page.extract_text() for page in PdfReader(io.BytesIO(r.content)).pages)


def test_the_owner_downloads_a_research_note(c, clean_db):
    a = ask(c).json()
    r = c.get(f"/api/answers/{a['id']}/pdf")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content[:4] == b"%PDF"
    assert "attachment" in r.headers["content-disposition"] and f"verdicta-answer-{a['id']}.pdf" in r.headers["content-disposition"]
    text = " ".join(pdf_text(r).split())
    assert a["question"] in text
    first = a["sentences"][0]
    assert first["text"][:40] in text                                  # the verified sentence
    assert first["citations"][0]["label"][:20] in text                 # its citation
    assert first["citations"][0]["quote"][:30] in text                 # the exact words quoted
    assert "not legal advice" in text


def test_nobody_else_downloads_it(c, clean_db):
    from app import main
    qid = ask(c).json()["id"]
    with TestClient(main.app, client=("203.0.113.7", 50001)) as other:
        assert other.get(f"/api/answers/{qid}/pdf").status_code == 404
        sign_up(other, "someone@example.com")
        assert other.get(f"/api/answers/{qid}/pdf").status_code == 404
    assert c.get("/api/answers/999999/pdf").status_code == 404


def test_no_pdf_for_an_error(c, clean_db, monkeypatch):
    from app import llm

    def broken(*a, **k):
        raise llm.ModelError("down")
    monkeypatch.setattr(llm, "ask_model", broken)
    qid = ask(c).json()["id"]
    assert c.get(f"/api/answers/{qid}/pdf").status_code == 400


def test_the_pdf_is_made_from_the_saved_answer_without_asking_again(c, clean_db, monkeypatch):
    from app import llm
    qid = ask(c).json()["id"]
    monkeypatch.setattr(llm, "ask_model", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no model call")))
    assert c.get(f"/api/answers/{qid}/pdf").status_code == 200
