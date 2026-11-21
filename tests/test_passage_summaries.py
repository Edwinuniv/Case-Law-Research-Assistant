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


@pytest.fixture(autouse=True)
def judge_says_yes(monkeypatch):
    """No test calls the real judge (Groq): it says "yes" unless a test sets another verdict (meaning check, 2026-11-21)."""
    monkeypatch.setattr(llm, "judge_summary", lambda statement, passage_text: "yes", raising=False)


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
    "What did the Court say about the passages of the Voting Rights Act it struck down?",   # a planted bug got through
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


def test_a_summary_is_not_a_turn_so_the_next_request_still_means_the_same_answer(model):
    """After "summarize passage 1", "now passage 2" must still find the 8 passages of the answer, not the 1 summarised."""
    r = pipeline.answer("summarize the first passage", NoSearch(), INDEX, ON, previous=TURN)
    assert pipeline.turn_of(r) is None


# ---------- widened (EVALUATION.md, 2026-11-21): citations, opinions, the case ----------
SYLLABUS = {**PASSAGE, "chunk_id": "1-1", "opinion_label": "Syllabus", "section": "Syllabus", "is_syllabus": True,
            "text": "Held: The President enjoys absolute immunity for actions within his conclusive and preclusive "
                    "constitutional authority."}
CONCURRENCE = {**PASSAGE, "chunk_id": "1-7", "opinion_label": "Concurrence", "section": "Barrett, J., concurring in part",
               "text": "I agree that the Constitution prohibits Congress from criminalizing the President's conduct."}
OTHER_CASE = {**PASSAGE, "chunk_id": "2-0", "decision_id": 222, "case_name": "Nixon v. Fitzgerald",
              "section": "Opinion of the Court (Powell)", "opinion_label": "Majority opinion"}
# the last answer cited P1 (majority) then P3 (majority); P2 is a dissent it did not cite
CITED = json.loads(json.dumps({**TURN, "sentences": [
    {"text": "a", "sources": ["P3"], "quote": QUOTE}, {"text": "b", "sources": ["P1", "P3"], "quote": QUOTE}]}))


class InsideSearch:
    """Records each search; returns passages of the decision asked for (and one of another decision when not limited)."""
    def __init__(self, found=(SYLLABUS, CONCURRENCE)):
        self.found, self.calls = list(found), []

    def search(self, q, k, decision_ids=None):
        self.calls.append(decision_ids)
        return [{**p, "score": 0.7} for p in self.found if decision_ids is None or p["decision_id"] in decision_ids] + \
            ([] if decision_ids else [{**OTHER_CASE, "score": 0.9}])

    def choose(self, q, found, top_k, use_reranker):
        return found[:top_k]


@pytest.mark.parametrize("text, which", [
    ("summarize the first citation", ["C1"]),
    ("explain the second citation", ["C2"]),
    ("summarize the citations", ["citations"]),
    ("summarize the dissent", ["opinion:dissent"]),
    ("what does the dissenting opinion say?", ["opinion:dissent"]),
    ("sum up the concurrence", ["opinion:concurrence"]),
    ("summarize the majority opinion", ["opinion:majority"]),
    ("summarise the syllabus", ["opinion:syllabus"]),
    ("summarize the case", ["case"]),
    ("can you explain this decision", ["case"]),
    ("summurize this case", ["case"]),
])
def test_citations_opinions_and_the_case_are_recognised(text, which):
    assert pipeline.passage_request(text) == which


@pytest.mark.parametrize("text", [
    "What did the dissent in Bostock v. Clayton County argue?",   # names a case: a normal question (eval-v1 A039)
    "Did the dissent say the case was wrongly decided?",          # no summarising verb: a question about the law
    "Summarize the dissent in Shelby County v. Holder",           # names a case
])
def test_a_question_naming_a_case_or_without_a_summarising_verb_is_not_a_request(text):
    assert pipeline.passage_request(text) is None


def test_a_citation_means_the_passages_the_answer_cited_in_order(model):
    pipeline.answer("summarize the first citation", NoSearch(), INDEX, ON, previous=CITED)
    pipeline.answer("summarize the second citation", NoSearch(), INDEX, ON, previous=CITED)
    pipeline.answer("summarize the citations", NoSearch(), INDEX, ON, previous=CITED)
    assert model == [["P3"], ["P1"], ["P1", "P3"]]


def test_a_citation_the_answer_did_not_show_gets_the_fixed_text(no_model):
    r = pipeline.answer("summarize the third citation", NoSearch(), INDEX, ON, previous=CITED)
    assert r["status"] == "WELCOME"


def test_an_opinion_in_the_last_answer_is_summarised_without_a_search(model):
    pipeline.answer("summarize the dissent", NoSearch(), INDEX, ON, previous=CITED)
    assert model == [["P2"]]


def test_an_opinion_not_in_the_last_answer_is_searched_only_inside_the_cited_decision(model):
    search = InsideSearch()
    r = pipeline.answer("sum up the concurrence", search, INDEX, ON, previous=CITED)
    assert search.calls == [[9987186]]                                 # the decision the answer cited, nothing else
    assert model == [["P4"]] and dict(r["passages"])["P4"]["chunk_id"] == "1-7"   # labelled after P3


def test_no_such_opinion_in_the_decision_gets_the_fixed_text(no_model):
    r = pipeline.answer("summarize the concurrence", InsideSearch(found=[SYLLABUS]), INDEX, ON, previous=CITED)
    assert r["status"] == "WELCOME" and "concurrence" in r["reason"].lower()


def test_the_case_is_the_cited_decisions_passages_plus_its_syllabus(model):
    search = InsideSearch()
    r = pipeline.answer("summarize the case", search, INDEX, ON, previous=CITED)
    sent = model[0]
    assert search.calls == [[9987186]] and {"P1", "P3"} <= set(sent)
    assert any(p["chunk_id"] == "1-1" for _, p in r["passages"])       # the syllabus was added
    assert all(p["decision_id"] == 9987186 for _, p in r["passages"])  # never another case


def test_with_no_earlier_answer_a_case_request_gets_the_fixed_text(no_model):
    assert pipeline.answer("summarize the case", NoSearch(), INDEX, ON)["status"] == "WELCOME"


def test_the_cases_syllabus_is_kept_even_when_the_search_finds_it_last(model):     # a planted bug got through
    many = [{**MAJORITY, "chunk_id": f"1-{n}"} for n in range(20, 25)] + [SYLLABUS]
    r = pipeline.answer("summarize the case", InsideSearch(found=many), INDEX, ON, previous=CITED)
    assert any(p["chunk_id"] == "1-1" for _, p in r["passages"])


def test_switched_on_a_request_in_a_follow_up_chat_is_a_summary_of_the_last_answer(model):
    r = pipeline.answer("summarize the dissent", NoSearch(), INDEX, ON, history=[CITED])
    assert model == [["P2"]] and r.get("passage_request") == ["opinion:dissent"]


# ---------- meaning check and instructions (EVALUATION.md, 2026-11-21: "Barrett argues ... subjective standard") ----------
@pytest.fixture
def judge(monkeypatch):
    """A fake judge: answers from `verdicts` (default "yes") and records what it was shown."""
    seen, verdicts = [], {}

    def fake(statement, passage_text):
        seen.append((statement, passage_text))
        v = verdicts.get("next", "yes")
        if v == "fail":
            raise llm.ModelError("rate limit reached, retry after 8 s")
        return v
    monkeypatch.setattr(llm, "judge_summary", fake)
    return seen, verdicts


def test_a_sentence_the_judge_says_yes_to_is_kept_and_it_saw_the_cited_passage(model, judge):
    seen, _ = judge
    r = pipeline.answer("summarize the first passage", NoSearch(), INDEX, ON, previous=TURN)
    assert r["shown_sentences"] and len(seen) == 1 and seen[0][1] == MAJORITY["text"]


@pytest.mark.parametrize("verdict", ["no", "partly", "fail"])
def test_a_sentence_the_judge_does_not_fully_support_is_removed(model, judge, verdict):
    judge[1]["next"] = verdict
    r = pipeline.answer("summarize the first passage", NoSearch(), INDEX, ON, previous=TURN)
    assert not r["shown_sentences"] and r["status"] == "NOT_SUPPORTED"
    assert r["removed"][0]["problems"] == ["the judge says the cited passage does not support it"]


def test_a_sentence_that_failed_the_six_checks_is_not_sent_to_the_judge(monkeypatch, judge):
    monkeypatch.setattr(llm, "ask_model", lambda *a, **k: {"status": "SUPPORTED", "sentences": [
        {"text": "The Court said so.", "sources": ["P1"], "quote": "words that are not in the passage at all"}]})
    pipeline.answer("summarize the first passage", NoSearch(), INDEX, ON, previous=TURN)
    assert judge[0] == []


def test_a_normal_question_is_never_judged(model, monkeypatch):
    monkeypatch.setattr(llm, "judge_summary", lambda *a: (_ for _ in ()).throw(AssertionError("no judge")))
    r = pipeline.answer("Is the President immune from prosecution?", OneSearch(), INDEX, ON, previous=TURN)
    assert r["shown_sentences"]


def test_the_model_is_told_whose_view_each_point_is_and_to_name_justices(monkeypatch, judge):
    asked = []
    monkeypatch.setattr(llm, "ask_model", lambda q, *a, **k: asked.append(q) or {"status": "NOT_SUPPORTED", "sentences": []})
    pipeline.answer("summarize the dissent", NoSearch(), INDEX, ON, previous=CITED)
    assert "whose view" in asked[0] and "pronoun" in asked[0]


def test_the_summary_judge_is_told_a_described_view_is_not_the_authors(monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "_ask_json", lambda system, user, *a, **k: calls.append((system, user)) or {"verdict": "no"})
    assert llm.judge_summary("Justice Barrett argues for a subjective standard.", "The Court adopts a subjective standard.") == "no"
    system, user = calls[0]
    assert system.startswith(llm.JUDGE_PROMPT.split("\n")[0]) and "someone else's view" in system
    assert "Justice Barrett argues" in user and "The Court adopts" in user
