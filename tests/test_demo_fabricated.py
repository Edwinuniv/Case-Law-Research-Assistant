"""Defence demo: a draft written as a lying model would write it goes through the REAL verifier; the invented
citation, the real citation of a case we did not retrieve and the invented case name are removed, the correct
sentence is kept. Written from the expected behaviour, before the code."""
from tests.test_citations import INDEX

PASSAGE = {"chunk_id": "1-0", "decision_id": 9987186, "opinion_id": 1, "case_name": "Trump v. United States",
           "score": 0.8, "opinion_label": "Opinion", "section": "",
           "text": "The President enjoys absolute immunity for actions within his conclusive and preclusive "
                   "constitutional authority, and the Court so holds today."}


def demo():
    from scripts.demo_fabricated import lying_draft, check
    draft = lying_draft({"P1": PASSAGE}, real_other="467 U.S. 837", invented="999 U.S. 9999")
    return draft, check(draft, {"P1": PASSAGE}, INDEX)


def test_the_lying_draft_has_one_honest_sentence_and_three_lies():
    draft, _ = demo()
    texts = [s["text"] for s in draft["sentences"]]
    assert len(texts) == 4 and "999 U.S. 9999" in texts[1] and "467 U.S. 837" in texts[2]
    assert all(s["sources"] == ["P1"] for s in draft["sentences"])


def test_only_the_honest_sentence_reaches_the_visitor():
    _, (kept, removed) = demo()
    assert [s["text"] for s in kept] == [demo()[0]["sentences"][0]["text"]]
    reasons = [p for s in removed for p in s["problems"]]
    assert any(p.startswith("FABRICATED citation") and "999 U.S. 9999" in p for p in reasons)
    assert any(p.startswith("real citation not supported") and "467 U.S. 837" in p for p in reasons)
    assert any(p.startswith("case name not in our corpus") for p in reasons)


def test_the_fabrication_is_counted():
    from app.verify import count_fabrications
    _, (_, removed) = demo()
    assert count_fabrications(removed) == 1                     # only the invented citation is provably invented
