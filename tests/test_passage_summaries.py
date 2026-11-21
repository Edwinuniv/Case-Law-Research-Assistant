"""Passage summaries (EVALUATION.md "Passage summaries", SPEC 11, 2026-11-21), written from the rule before the code.
"summurize the first passage" after a Counterman answer was answered about another case on the live site: a passage
request now uses ONLY the passages of the last answer, with no search, and the same verifier."""
import json
import pytest
from app import pipeline, llm
from app.config import DEFAULT_SETTINGS
from tests.test_citations import INDEX
from tests.test_verify import PASSAGE, QUOTE

ON = dict(DEFAULT_SETTINGS, passage_summaries=True)
OFF = dict(DEFAULT_SETTINGS, passage_summaries=False)

DISSENT = {**PASSAGE, "chunk_id": "1-9", "opinion_label": "Dissent", "section": "Sotomayor, J., dissenting",
           "text": "With fear for our democracy, I dissent. The President is now a king above the law."}
MAJORITY = {**PASSAGE, "opinion_label": "Majority opinion", "section": "Opinion of the Court (Roberts)",
            "date_filed": "2024-07-01"}
# the last answer as a chat keeps it (pipeline.turn_of, stored as JSON: the passages are [label, passage] pairs)
TURN = json.loads(json.dumps({"question": "Is the President immune?", "sentences": [],
                              "passages": [["P1", MAJORITY], ["P2", DISSENT], ["P3", MAJORITY]]}))


class NoSearch:
    def search(self, *a, **k):
        raise AssertionError("a passage request must not search")

    def choose(self, *a, **k):
        raise AssertionError("a passage request must not search")


class OneSearch:
    def __init__(self):
        self.calls = 0

    def search(self, q, k, **kw):
        self.calls += 1
        return [{**MAJORITY, "score": 0.9}]

    def choose(self, q, found, top_k, use_reranker):
        return found[:top_k]


@pytest.fixture
def model(monkeypatch):
    """A fake model that summarises P1 correctly and records the passages it received."""
    got = []

    def fake(question, passages, *a, **k):
        got.append(sorted(passages))
        return {"status": "SUPPORTED", "sentences": [
            {"text": "The Court held that the President has absolute immunity for conclusive and preclusive actions.",
             "sources": ["P1"], "quote": QUOTE}]}
    monkeypatch.setattr(llm, "ask_model", fake)
    return got


@pytest.fixture
def no_model(monkeypatch):
    monkeypatch.setattr(llm, "ask_model", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no model call")))


# ---------- which messages are passage requests ----------
@pytest.mark.parametrize("text, which", [
    ("summarize the first passage", ["P1"]),
    ("summurize the first passage", ["P1"]),                     # the live message, misspelt
    ("Summarise passage 2", ["P2"]),
    ("explain P3", ["P3"]),
    ("what does p2 say?", ["P2"]),
    ("summarize the second and third passages", ["P2", "P3"]),
    ("summarize passages 1 and 3", ["P1", "P3"]),
    ("summarize the last passage", ["last"]),
    ("summarize all the passages", ["all"]),
    ("can you summarize these passages", ["all"]),
])
def test_a_request_about_the_passages_is_recognised(text, which):
    assert pipeline.passage_request(text) == which


@pytest.mark.parametrize("text", [
    "What did the passage of the Affordable Care Act change?",   # "passage" of a law, not of the answer
    "Was Chevron overruled?",
    "What does the First Amendment say about true threats?",
    "Summarize Obergefell v. Hodges",                            # a case, not a passage: the normal pipeline
    "Is passage of time relevant to laches?",
])
def test_a_legal_question_is_not_a_passage_request(text):
    assert pipeline.passage_request(text) is None


def test_no_test_question_is_a_passage_request():                       # the evaluation numbers stay valid
    with open("eval/questions.jsonl") as f:
        questions = [json.loads(line)["question"] for line in f if line.strip()]
    assert len(questions) == 85 and not [q for q in questions if pipeline.passage_request(q)]


# ---------- with the last answer: only its passages, no search, the same verifier ----------
def test_the_model_gets_only_the_requested_passages_and_nothing_is_searched(model):
    r = pipeline.answer("summarize the first passage", NoSearch(), INDEX, ON, previous=TURN)
    assert model == [["P1"]]
    assert r["status"] in ("ANSWERED", "LOW_CONFIDENCE") and r["shown_sentences"]
    assert [pid for pid, _ in r["passages"]] == ["P1"]          # the passages panel shows what was summarised


def test_all_and_last_mean_the_last_answers_passages(model):
    pipeline.answer("summarize all the passages", NoSearch(), INDEX, ON, previous=TURN)
    pipeline.answer("summarize the last passage", NoSearch(), INDEX, ON, previous=TURN)
    assert model == [["P1", "P2", "P3"], ["P3"]]


def test_a_sentence_citing_a_passage_that_was_not_requested_is_removed(monkeypatch):
    monkeypatch.setattr(llm, "ask_model", lambda *a, **k: {"status": "SUPPORTED", "sentences": [
        {"text": "The dissent said the President is now a king above the law.", "sources": ["P2"],
         "quote": "The President is now a king above the law"}]})
    r = pipeline.answer("summarize the first passage", NoSearch(), INDEX, ON, previous=TURN)
    assert r["status"] == "NOT_SUPPORTED" and not r["shown_sentences"]
    assert "cites a passage that was not sent to the model" in r["removed"][0]["problems"]


def test_a_dissent_summarised_as_the_court_is_removed(monkeypatch):           # check 6 still applies
    monkeypatch.setattr(llm, "ask_model", lambda *a, **k: {"status": "SUPPORTED", "sentences": [
        {"text": "The Court held that the President is now a king above the law.", "sources": ["P2"],
         "quote": "The President is now a king above the law"}]})
    r = pipeline.answer("explain passage 2", NoSearch(), INDEX, ON, previous=TURN)
    assert not r["shown_sentences"]


def test_a_model_error_is_an_error(monkeypatch):
    def broken(*a, **k):
        raise llm.ModelError("rate limit reached, retry after 8 s")
    monkeypatch.setattr(llm, "ask_model", broken)
    assert pipeline.answer("summarize passage 1", NoSearch(), INDEX, ON, previous=TURN)["status"] == "ERROR"


# ---------- no earlier answer, a passage it did not have, or switched off: our fixed text ----------
def test_with_no_earlier_answer_a_fixed_text_and_no_search_or_model(no_model):
    r = pipeline.answer("summurize the first passage", NoSearch(), INDEX, ON)
    assert r["status"] == "WELCOME" and "passage" in r["reason"].lower() and not r["shown_sentences"]


def test_a_passage_the_last_answer_did_not_have_gets_the_fixed_text(no_model):
    r = pipeline.answer("summarize passage 7", NoSearch(), INDEX, ON, previous=TURN)
    assert r["status"] == "WELCOME" and "P1-P3" in r["reason"]


def test_switched_off_a_request_gets_the_fixed_text_and_never_another_case(no_model):
    r = pipeline.answer("summarize the first passage", NoSearch(), INDEX, OFF, previous=TURN)
    assert r["status"] == "WELCOME" and "passages" in r["reason"].lower()


def test_off_is_the_default_until_the_measurement():
    assert not DEFAULT_SETTINGS.get("passage_summaries", False)


def test_a_normal_question_with_an_earlier_answer_goes_through_the_pipeline(model):
    search = OneSearch()
    r = pipeline.answer("Is the President immune from prosecution?", search, INDEX, ON, previous=TURN)
    assert search.calls == 1 and r["status"] in ("ANSWERED", "LOW_CONFIDENCE")
