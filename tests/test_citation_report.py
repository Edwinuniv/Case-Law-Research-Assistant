"""Week 8, step 8.3: the report of every citation shown and removed in a saved run (scripts/show_citations.py)."""
from app.config import DEFAULT_SETTINGS
from tests.test_evaluate import q, res

S = dict(DEFAULT_SETTINGS)

def removed(text, problem, sources=("P1",)):
    return {"text": text, "sources": list(sources), "quote": "...", "problems": [problem]}

def test_a_citation_problem_counts_only_if_the_sentence_was_shown():      # FR16, SR38
    from scripts.show_citations import collect
    shown = {**res(0.9, false=("citation does not exist: 1 U.S. 1",)), "removed": []}
    hidden = {**res(0.1, false=("citation does not exist: 2 U.S. 2",)), "removed": []}   # NOT_SUPPORTED: nothing shown
    report = collect([(q("a", "answerable"), shown), (q("b", "answerable"), hidden)], S)
    assert [(x["id"], x["problem"]) for x in report["shown"]] == [("a", "citation does not exist: 1 U.S. 1")]

def test_removed_citations_and_case_names_are_listed_but_not_other_removals():
    from scripts.show_citations import collect
    r = {**res(0.9), "removed": [removed("See 599 U.S. 412.", "FABRICATED citation (not in the citation table): 599 U.S. 412"),
                                 removed("In Trump v. Anything...", "case name not in our corpus or the cited passage: Trump v. Anything"),
                                 removed("Five to four.", "number or date not in the cited passage: 5")]}
    report = collect([(q("a", "adversarial"), r)], S)
    assert [x["problem"].split(":")[0] for x in report["removed"]] == ["FABRICATED citation (not in the citation table)",
                                                                       "case name not in our corpus or the cited passage"]

def test_a_quote_not_found_is_traced_to_its_decision():
    from scripts.show_citations import collect
    r = {**res(0.9, ranked=(5, 7, 9)), "removed": [removed("x", "quote not found in the cited passage", sources=("P2",))]}
    assert collect([(q("a", "answerable"), r)], S)["quote_not_found"] == {7: 1}       # P2 = 2nd passage = decision 7

def test_only_the_tune_split_and_adversarial_questions_by_default():        # SR29: TEST looked at once, at the end
    from scripts.show_citations import keep_split
    pairs = [({**q("t", "answerable"), "split": "tune"}, {}), (q("s", "answerable"), {}), (q("x", "adversarial"), {})]
    assert [p["id"] for p, _ in keep_split(pairs, "tune")] == ["t", "x"]


def test_a_saved_run_file_can_be_reported(monkeypatch, capsys):                # the rechecked run 2 is a file
    from scripts import show_citations
    pairs = [({**q("t", "answerable"), "split": "tune"}, {**res(0.9), "removed": []})]
    monkeypatch.setattr(show_citations.evaluate, "load_run_file", lambda path: pairs)
    monkeypatch.setattr(show_citations.evaluate, "load_run", lambda run_id: [])
    monkeypatch.setattr(show_citations.db, "get_settings", lambda: S)
    show_citations.main(["eval/runs/eval_run2_reverified.json"])
    assert "1 questions" in capsys.readouterr().out
