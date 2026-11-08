"""Which citation the answer shows for a decision (asked by Edwin after the Week 8 run).
A decision can have several citations in CourtListener, and the first one is sometimes an odd reporter
(Nelson v. Adams: "0 Cal. Daily Op. Serv. 3128"). Expected behaviour, written before the code: show the
official U.S. Reports citation first, then the Supreme Court Reporter (S. Ct.), then the Lawyers' Edition
(L. Ed.); if there is none of them, the first citation as before; with no citation, the docket number.
Edwin's checker uses the same order, so the page and the evaluation agree."""
from app import api
from tests.test_api_research import c, ask                    # noqa: F401 (c is the fixture)

ODD = "0 Cal. Daily Op. Serv. 3128"


def test_us_reports_first_wherever_it_is():
    assert api.best_citation([ODD, "128 S. Ct. 2229", "553 U.S. 723"]) == "553 U.S. 723"
    assert api.best_citation(["553 U.S. 723", ODD]) == "553 U.S. 723"


def test_then_supreme_court_reporter_then_lawyers_edition():
    assert api.best_citation([ODD, "171 L. Ed. 2d 41", "128 S. Ct. 2229"]) == "128 S. Ct. 2229"
    assert api.best_citation([ODD, "171 L. Ed. 2d 41"]) == "171 L. Ed. 2d 41"
    assert api.best_citation([ODD, "45 L. Ed. 100"]) == "45 L. Ed. 100"


def test_other_reporters_keep_the_first_one():
    assert api.best_citation([ODD, "2008 U.S. LEXIS 4887"]) == ODD        # U.S. LEXIS is not U.S. Reports


def test_label_without_citation_shows_the_docket_number():
    p = {"case_name": "Some v. Case", "date_filed": "2020-01-01", "opinion_label": "Majority opinion"}
    assert api.citation_label(p, {"citations": [], "docket_number": "19-123"}) == \
        "Some v. Case, No. 19-123 (2020) · Majority opinion"


def test_the_answer_shows_the_us_reports_citation(c, clean_db):
    with clean_db.connect() as con:
        con.execute("UPDATE decisions SET citations = %s WHERE decision_id = 9987186",
                    ([ODD, "144 S. Ct. 2312", "603 U.S. 593"],))
    r = ask(c).json()
    assert r["sentences"][0]["citations"][0]["label"] == "Trump v. United States, 603 U.S. 593 (2024) · Majority opinion"
    assert r["passages"][0]["label"].startswith("Trump v. United States, 603 U.S. 593")
