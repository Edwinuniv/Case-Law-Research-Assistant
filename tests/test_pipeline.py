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



# --- A welcome message instead of "not supported" for greetings and "what can you do" (2026-11-12, Edwin) ---
# Fixed text written by us, never by the model: no search, no model call, no legal statement (FR2, NFR2, SR28).
# The instructor's rule stays: one independent question per message, no follow-up questions (SPEC section 11).
class NoSearch:
    def search(self, *a, **k): raise AssertionError("a greeting must not be searched")
    def choose(self, *a, **k): raise AssertionError("a greeting must not be searched")

@pytest.mark.parametrize("text", ["hello what can you do", "Hello!", "hi there, what can you do?", "Help",
                                  "Who are you?", "Good morning. How does this work?", "hey", "thanks"])
def test_a_greeting_gets_the_welcome_message_without_search_or_model(monkeypatch, text):
    monkeypatch.setattr(llm, "ask_model", lambda q, p: (_ for _ in ()).throw(AssertionError("no model call")))
    r = pipeline.answer(text, NoSearch(), INDEX, S)
    assert r["status"] == "WELCOME" and r["shown_sentences"] == [] and r["passages"] == []
    assert "Supreme Court" in r["reason"] and "2000" in r["reason"]          # what Verdicta does and its coverage

@pytest.mark.parametrize("text", ["Hello, did the Supreme Court overrule Chevron deference?",
                                  "Hi, what did the Court hold in Bostock v. Clayton County?",
                                  "help me find the holding of Roe v. Wade",
                                  "What can you tell me about the Second Amendment?"])
def test_a_legal_question_with_a_greeting_goes_through_the_pipeline(monkeypatch, text):
    monkeypatch.setattr(llm, "ask_model", good_model)
    assert pipeline.answer(text, FakeSearcher(0.9), INDEX, S)["status"] != "WELCOME"

def test_no_test_question_is_taken_for_a_greeting():                  # the evaluation numbers stay valid
    import json
    from pathlib import Path
    questions = [json.loads(l)["question"] for l in Path("eval/questions.jsonl").read_text().splitlines() if l.strip()]
    assert len(questions) == 85 and not [q for q in questions if pipeline.is_greeting(q)]


# --- Answer v2 (EVALUATION.md "Answer v2 rule", 2026-11-13): follow-ups that read the chat, "not about the law" ---
V2 = dict(S, prompt_version="v2")

def chunk(n, decision, text=None):
    return {**PASSAGE, "chunk_id": f"c{n}", "decision_id": decision, "score": 0.9, "text": text or PASSAGE["text"],
            "opinion_label": "Majority opinion", "section": "Part I", "date_filed": "2024-07-01"}

class Recorder:
    """A searcher that returns the given chunks and remembers the query it was asked."""
    def __init__(self, chunks): self.chunks, self.queries = chunks, []
    def search(self, q, k, **kw): self.queries.append(q); return self.chunks
    def choose(self, q, found, top_k, use_reranker): return found[:top_k]

FIRST_TURN = {"question": "Is the President immune?", "passages": [("P1", chunk(1, 9987186))],
              "sentences": [{"text": "The President has absolute immunity for conclusive and preclusive actions.",
                             "sources": ["P1"], "quote": QUOTE}]}

def model_spy(calls, reply=None):
    def ask(q, passages, history=None, version="v1"):
        calls.append({"question": q, "passages": dict(passages), "history": history, "version": version})
        return reply or {"status": "SUPPORTED", "sentences": [{"text": "The President has absolute immunity for conclusive actions.",
                                                               "sources": ["P1"], "quote": QUOTE}]}
    return ask

def test_a_follow_up_reads_the_chat_and_searches_with_the_earlier_question(monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "ask_model", model_spy(calls))
    searcher = Recorder([chunk(2, 9987186)])
    r = pipeline.answer("And for unofficial acts?", searcher, INDEX, V2, history=[FIRST_TURN])
    assert "Is the President immune?" in searcher.queries[0] and "And for unofficial acts?" in searcher.queries[0]
    assert calls[0]["history"] == [FIRST_TURN] and calls[0]["version"] == "v2"
    assert r["status"] in ("ANSWERED", "LOW_CONFIDENCE")             # it cites P1, a passage of the earlier turn

def test_same_topic_adds_at_most_4_new_passages_new_topic_up_to_8_never_twice(monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "ask_model", model_spy(calls))
    same = [chunk(1, 9987186)] + [chunk(n, 9987186) for n in range(2, 12)]      # c1 was already sent
    pipeline.answer("And the dissent?", Recorder(same), INDEX, V2, history=[FIRST_TURN])
    assert list(calls[-1]["passages"]) == ["P2", "P3", "P4", "P5"]                # new labels after P1, c1 not sent again
    assert [p["chunk_id"] for p in calls[-1]["passages"].values()] == ["c2", "c3", "c4", "c5"]
    other = [chunk(n, 5555) for n in range(20, 31)]
    pipeline.answer("What about Chevron?", Recorder(other), INDEX, V2, history=[FIRST_TURN])
    assert list(calls[-1]["passages"]) == [f"P{n}" for n in range(2, 10)]          # a new topic: up to 8

def test_a_sentence_may_cite_an_earlier_passage_but_not_a_label_that_was_never_sent(monkeypatch):
    bad = {"status": "SUPPORTED", "sentences": [{"text": "It is immune.", "sources": ["P9"], "quote": QUOTE}]}
    monkeypatch.setattr(llm, "ask_model", model_spy([], bad))
    r = pipeline.answer("And why?", Recorder([]), INDEX, V2, history=[FIRST_TURN])
    assert r["shown_sentences"] == [] and "not sent" in r["removed"][0]["problems"][0]

def test_only_the_last_turns_are_kept(monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "ask_model", model_spy(calls))
    turns = [{**FIRST_TURN, "question": f"Question {n}?"} for n in range(10)]
    pipeline.answer("And then?", Recorder([]), INDEX, dict(V2, followup_max_turns=3), history=turns)
    assert [t["question"] for t in calls[0]["history"]] == ["Question 7?", "Question 8?", "Question 9?"]

def test_a_question_not_about_the_law_gets_the_assistant_message(monkeypatch):
    monkeypatch.setattr(llm, "ask_model", model_spy([], {"status": "OFF_TOPIC", "sentences": []}))
    r = pipeline.answer("Which football team is the best?", FakeSearcher(0.9), INDEX, V2)
    assert r["status"] == "NOT_SUPPORTED" and r["off_topic"] and "case-law research assistant" in r["reason"]
    assert r["shown_sentences"] == []                                   # counted as an abstention, nothing generated

def test_an_independent_question_with_the_old_prompt_calls_the_model_as_before(monkeypatch):    # rule (4)
    seen = []
    monkeypatch.setattr(llm, "ask_model", lambda q, p: seen.append((q, list(p))) or good_model(q, p))
    r = pipeline.answer("Is the President immune?", FakeSearcher(0.9), INDEX, S)       # no history, prompt v1
    assert r["status"] == "ANSWERED" and seen == [("Is the President immune?", ["P1"])]
