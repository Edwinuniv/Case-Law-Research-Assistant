import pytest
from app import pipeline, llm
from app.config import DEFAULT_SETTINGS
from tests.test_citations import INDEX
from tests.test_verify import PASSAGE, QUOTE

S = dict(DEFAULT_SETTINGS, tau_abstain=0.55)   # these tests were written for the guide's 0.55; the live value is chosen on TUNE (EVALUATION.md)

class FakeSearcher:
    def __init__(self, score): self.score = score
    def search(self, q, k): return [{**PASSAGE, "score": self.score, "opinion_label": "Majority opinion",
                                     "section": "Part I", "date_filed": "2024-07-01"}]
    def choose(self, q, found, top_k, use_reranker): return found[:top_k]

def good_model(q, p):
    return {"status": "SUPPORTED", "sentences": [{"text": "The President has absolute immunity for conclusive and preclusive actions.",
                                                  "sources": ["P1"], "quote": QUOTE}]}

def test_input_length_is_checked():                       # SR3
    assert pipeline.check_input("ab") and pipeline.check_input("x" * 1001)
    assert pipeline.check_input("Is the President immune?") is None

def test_low_similarity_abstains_without_calling_the_model(monkeypatch):
    called = []
    monkeypatch.setattr(llm, "ask_model", lambda q, p: called.append(1))
    r = pipeline.answer("What about tax law?", FakeSearcher(0.1), INDEX, S)
    assert r["status"] == "NOT_SUPPORTED" and not called

def test_good_answer(monkeypatch):
    monkeypatch.setattr(llm, "ask_model", good_model)
    r = pipeline.answer("Is the President immune?", FakeSearcher(0.9), INDEX, S)
    assert r["status"] == "ANSWERED" and len(r["shown_sentences"]) == 1 and r["support_score"] >= S["tau_confident"]

def test_model_says_not_supported(monkeypatch):
    monkeypatch.setattr(llm, "ask_model", lambda q, p: {"status": "NOT_SUPPORTED", "sentences": []})
    assert pipeline.answer("Is the President immune?", FakeSearcher(0.9), INDEX, S)["status"] == "NOT_SUPPORTED"

def test_fabricating_model_never_reaches_the_visitor(monkeypatch):
    monkeypatch.setattr(llm, "ask_model", lambda q, p: {"status": "SUPPORTED", "sentences": [
        {"text": "See Fake v. Case, 999 U.S. 9999.", "sources": ["P1"], "quote": QUOTE}]})
    r = pipeline.answer("Is the President immune?", FakeSearcher(0.9), INDEX, S)
    assert r["status"] == "NOT_SUPPORTED" and r["fabrications_caught"] >= 1 and r["shown_sentences"] == []

def test_model_failure_gives_error(monkeypatch):
    def broken(q, p): raise llm.ModelError("timeout after 30 seconds")
    monkeypatch.setattr(llm, "ask_model", broken)
    assert pipeline.answer("Is the President immune?", FakeSearcher(0.9), INDEX, S)["status"] == "ERROR"

def test_weak_support_is_low_confidence():
    kept = [{"sources": ["P1"], "groundedness": 0.5}]
    score = pipeline.support_score(kept, [], {"P1": {"score": 0.6}}, S)
    assert pipeline.decide(score, 1, S) in ("LOW_CONFIDENCE", "NOT_SUPPORTED")
    assert pipeline.decide(0.9, 1, S) == "ANSWERED" and pipeline.decide(0.9, 0, S) == "NOT_SUPPORTED"


# --- Not in the guide: tests for gaps found by breaking the code on purpose (see AI_LOG.md) ---

def test_not_supported_hides_sentences_that_passed_verification(monkeypatch):     # SR28
    def half_fabricated(q, p):
        good = good_model(q, p)["sentences"][0]
        return {"status": "SUPPORTED", "sentences": [good, {"text": "See Fake v. Case, 999 U.S. 9999.",
                                                            "sources": ["P1"], "quote": QUOTE}]}
    monkeypatch.setattr(llm, "ask_model", half_fabricated)
    r = pipeline.answer("Is the President immune?", FakeSearcher(0.9), INDEX, S)
    assert r["status"] == "NOT_SUPPORTED" and len(r["sentences"]) == 1 and r["shown_sentences"] == []


# --- Metadata (2026-11-06): a case named in the question limits the search to its decision ---
class FilterSearcher(FakeSearcher):
    def __init__(self):
        super().__init__(0.8)
        self.decision_ids = "not called"
    def search(self, q, k, decision_ids=None):
        self.decision_ids = decision_ids
        return super().search(q, k)

LOPER_QUESTION = "What did the Court decide in Loper Bright Enterprises v. Raimondo about Chevron?"

def test_named_case_limits_the_search_to_its_decision(monkeypatch):
    monkeypatch.setattr(llm, "ask_model", good_model)
    searcher = FilterSearcher()
    r = pipeline.answer(LOPER_QUESTION, searcher, INDEX, dict(S, case_filter=True))
    assert searcher.decision_ids == [9986254] and r["case_filter"] == [9986254]

def test_case_filter_is_off_unless_switched_on(monkeypatch):
    # With the setting off, the normal search runs; a searcher without the decision_ids parameter
    # (search(q, k)) must still work. (The default is on since the measurement: EVALUATION.md.)
    monkeypatch.setattr(llm, "ask_model", good_model)
    r = pipeline.answer(LOPER_QUESTION, FakeSearcher(0.8), INDEX, dict(S, case_filter=False))
    assert r["status"] == "ANSWERED" and r["case_filter"] == []

def test_invented_or_mixed_name_uses_the_normal_search(monkeypatch):
    monkeypatch.setattr(llm, "ask_model", good_model)
    for question in ("Summarise Halvorsen v. Pacific Grain Co., 598 U.S. 377 (2023).",
                     "What did the Court hold in Trump v. Raimondo?", "Is the President immune?"):
        searcher = FilterSearcher()
        pipeline.answer(question, searcher, INDEX, dict(S, case_filter=True))
        assert searcher.decision_ids is None, question

