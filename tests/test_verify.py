from app.verify import verify, numbers_in
from tests.test_citations import INDEX

PASSAGE = {"chunk_id": "1-0", "decision_id": 9987186, "opinion_id": 1, "case_name": "Trump v. United States",
           "score": 0.8, "text": "The President enjoys absolute immunity for actions within his conclusive and "
                                 "preclusive constitutional authority. The indictment was returned in 2023. "
                                 "See Chevron U.S.A. Inc. v. NRDC, 467 U.S. 837 (1984)."}
P = {"P1": PASSAGE}
QUOTE = "enjoys absolute immunity for actions within his conclusive"

def run(text, sources=("P1",), quote=QUOTE):
    return verify({"sentences": [{"text": text, "sources": list(sources), "quote": quote}]}, P, INDEX)

def test_good_sentence_is_kept_with_groundedness():
    kept, removed = run("The President has absolute immunity for conclusive and preclusive actions.")
    assert len(kept) == 1 and not removed and kept[0]["groundedness"] > 0.5

def test_passage_that_was_not_sent_is_removed():
    kept, removed = run("Something.", sources=["P9"])
    assert not kept

def test_sentence_without_passage_is_removed():
    kept, removed = run("Something.", sources=[])
    assert not kept

def test_changed_quote_is_removed():
    kept, removed = run("x", quote="enjoys limited immunity for actions within his conclusive")
    assert not kept and "quote" in removed[0]["problems"][0]

def test_fabricated_citation_is_removed_and_labelled():
    kept, removed = run("See Henderson v. Atlantic Maritime, 599 U.S. 412.")
    assert not kept and any(p.startswith("FABRICATED") for p in removed[0]["problems"])

def test_citation_of_a_retrieved_decision_is_allowed():
    kept, _ = run("This is the rule of 603 U.S. 593.")
    assert kept

def test_citation_written_in_the_passage_is_allowed():
    kept, _ = run("The opinion cites 467 U.S. 837.")
    assert kept

def test_number_not_in_passage_is_removed():            # SR25
    kept, removed = run("The indictment was returned in 2021.")
    assert not kept and "2021" in removed[0]["problems"][0]

def test_number_in_passage_is_allowed():
    kept, _ = run("The indictment was returned in 2023.")
    assert kept

def test_numbers_ignore_commas():
    assert numbers_in("It cost $1,000,000.") == {"1000000"}


# --- Not in the guide: tests for gaps found by breaking the code on purpose (see AI_LOG.md) ---

def test_fabricated_citation_without_a_case_name_is_caught():          # check 3 on its own, SR23
    kept, removed = run("As held in 599 U.S. 412, the immunity is absolute.")
    assert not kept and any(p.startswith("FABRICATED citation") for p in removed[0]["problems"])

def test_passage_markers_are_not_numbers_and_are_not_shown():
    kept, _ = run('The indictment was returned in 2023. ["P1"]')
    assert kept and "P1" not in kept[0]["text"]
