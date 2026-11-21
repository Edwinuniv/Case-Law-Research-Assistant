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


def first_words(passage, n=8):
    return " ".join(passage["text"].split()[:n])


@pytest.fixture
def model(monkeypatch):
    """Fake models that record the passages they received: the picker (summaries, option A, 2026-11-21) picks the first
    8 words of each passage, word for word; the normal model answers a normal question correctly."""
    got = []

    def pick(question, passages, *a, **k):
        got.append(sorted(passages))
        return {"picks": [{"passage": pid, "sentence": first_words(p)} for pid, p in passages.items()]}

    def write(question, passages, *a, **k):
        got.append(sorted(passages))
        return {"status": "SUPPORTED", "sentences": [
            {"text": "The Court held that the President has absolute immunity for conclusive and preclusive actions.",
             "sources": ["P1"], "quote": QUOTE}]}
    monkeypatch.setattr(llm, "pick_sentences", pick, raising=False)
    monkeypatch.setattr(llm, "ask_model", write)
    return got


def picks(monkeypatch, *chosen):
    """The picker returns exactly these (passage, sentence) picks."""
    monkeypatch.setattr(llm, "pick_sentences", lambda *a, **k: {"picks": [{"passage": p, "sentence": t} for p, t in chosen]},
                        raising=False)


@pytest.fixture
def no_model(monkeypatch):
    never = lambda *a, **k: (_ for _ in ()).throw(AssertionError("no model call"))   # noqa: E731
    monkeypatch.setattr(llm, "ask_model", never)
    monkeypatch.setattr(llm, "pick_sentences", never, raising=False)


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


def test_a_pick_from_a_passage_that_was_not_requested_is_removed(monkeypatch):
    picks(monkeypatch, ("P2", "The President is now a king above the law"))
    r = pipeline.answer("summarize the first passage", NoSearch(), INDEX, ON, previous=TURN)
    assert r["status"] == "NOT_SUPPORTED" and not r["shown_sentences"]
    assert "cites a passage that was not sent to the model" in r["removed"][0]["problems"]


def test_the_page_shows_the_passages_own_words_after_its_label_never_the_models_words(monkeypatch):
    monkeypatch.setattr(llm, "pick_sentences", lambda *a, **k: {"picks": [
        {"passage": "P2", "sentence": "The President is now a king above the law",
         "text": "The Court held that the President is a king."}]}, raising=False)        # a retelling is ignored
    r = pipeline.answer("explain passage 2", NoSearch(), INDEX, ON, previous=TURN)
    (shown,) = r["shown_sentences"]
    assert shown["text"] == "Sotomayor, J., dissenting: \u201cThe President is now a king above the law\u201d"
    assert shown["sources"] == ["P2"] and shown["quote"] == "The President is now a king above the law"


def test_a_pick_that_is_not_word_for_word_is_removed(monkeypatch):            # the Barrett case: a retold view
    picks(monkeypatch, ("P2", "The President is a king and above every law"))
    r = pipeline.answer("explain passage 2", NoSearch(), INDEX, ON, previous=TURN)
    assert not r["shown_sentences"] and r["removed"][0]["problems"] == ["quote not found in the cited passage"]


def test_a_pick_under_five_words_is_removed(monkeypatch):
    picks(monkeypatch, ("P2", "I dissent"))
    assert not pipeline.answer("explain passage 2", NoSearch(), INDEX, ON, previous=TURN)["shown_sentences"]


def test_at_most_three_picks_per_passage_and_eight_in_all_in_passage_order(monkeypatch):
    many = {f"P{n}": {**MAJORITY, "chunk_id": f"1-{n}"} for n in range(1, 6)}
    turn = json.loads(json.dumps({"question": "q", "sentences": [], "passages": list(many.items())}))
    words = MAJORITY["text"].split()
    chosen = [(f"P{n}", " ".join(words[i:i + 6])) for n in (5, 4, 3, 2, 1) for i in (0, 3, 6, 9)]   # 4 each, reversed
    picks(monkeypatch, *chosen)
    r = pipeline.answer("summarize all the passages", NoSearch(), INDEX, ON, previous=turn)
    order = [s["sources"][0] for s in r["shown_sentences"]]
    assert len(order) == 8 and order == ["P1"] * 3 + ["P2"] * 3 + ["P3"] * 2


def test_no_valid_pick_is_not_supported(monkeypatch):
    picks(monkeypatch)
    r = pipeline.answer("explain passage 2", NoSearch(), INDEX, ON, previous=TURN)
    assert r["status"] == "NOT_SUPPORTED" and not r["shown_sentences"]


def test_a_model_error_is_an_error(monkeypatch):
    def broken(*a, **k):
        raise llm.ModelError("rate limit reached, retry after 8 s")
    monkeypatch.setattr(llm, "pick_sentences", broken, raising=False)
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



def test_the_picker_is_told_to_copy_sentences_word_for_word(monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "_ask_json", lambda system, user, *a, **k: calls.append((system, user)) or {"picks": []})
    llm.pick_sentences("summarize the dissent", {"P2": {**DISSENT, "date_filed": "2024-07-01"}})   # as every real passage
    system, user = calls[0]
    assert "word for word" in system and "[P2]" in user and DISSENT["text"] in user and "summarize the dissent" in user


# ---------- before run 2 (EVALUATION.md: run 1 showed "Glucksberg, 521 U.S. 701" from the source, and "Part II") ----------
WITH_CITES = {**MAJORITY, "text": "As the Court said in Fake v. Case, 999 U.S. 9999 (2001), the power is limited. "
                                  "See Chevron U.S.A. Inc. v. NRDC, 467 U.S. 837 (1984) for the old rule of deference."}
TURN_CITES = json.loads(json.dumps({"question": "q", "sentences": [], "passages": [["P1", WITH_CITES]]}))


def test_a_pick_with_a_citation_that_is_not_in_the_table_is_removed_even_if_the_source_says_it(monkeypatch):
    picks(monkeypatch, ("P1", "As the Court said in Fake v. Case, 999 U.S. 9999 (2001), the power is limited."))
    r = pipeline.answer("summarize the first passage", NoSearch(), INDEX, ON, previous=TURN_CITES)
    assert not r["shown_sentences"] and "citation" in r["removed"][0]["problems"][0]


CHEVRON = "See Chevron U.S.A. Inc. v. NRDC, 467 U.S. 837 (1984) for the old rule of deference."


def test_a_real_citation_in_the_opinions_citation_map_is_kept(monkeypatch):            # rule (f), before run 4
    asked = []
    monkeypatch.setattr(pipeline, "in_citation_map", lambda opinions, clusters: asked.append((opinions, clusters)) or True,
                        raising=False)
    picks(monkeypatch, ("P1", CHEVRON))
    assert pipeline.answer("summarize the first passage", NoSearch(), INDEX, ON, previous=TURN_CITES)["shown_sentences"]
    assert asked == [([WITH_CITES["opinion_id"]], [111])]       # the passage's opinion, the citation's clusters


def test_a_real_citation_outside_the_passages_and_the_citation_map_is_removed(monkeypatch):   # run 3: Blodgett
    monkeypatch.setattr(pipeline, "in_citation_map", lambda opinions, clusters: False, raising=False)
    picks(monkeypatch, ("P1", CHEVRON))
    r = pipeline.answer("summarize the first passage", NoSearch(), INDEX, ON, previous=TURN_CITES)
    assert not r["shown_sentences"]
    assert r["removed"][0]["problems"] == ["citation not from a passage sent or its citation map: 467 U.S. 837"]


def test_a_citation_of_a_passage_sent_needs_no_citation_map(monkeypatch):
    monkeypatch.setattr(pipeline, "in_citation_map", lambda *a: (_ for _ in ()).throw(AssertionError("not needed")),
                        raising=False)
    passage = {**MAJORITY, "text": "As the Court held in Trump v. United States, 603 U.S. 593 (2024), the immunity is absolute."}
    turn = json.loads(json.dumps({"question": "q", "sentences": [], "passages": [["P1", passage]]}))
    picks(monkeypatch, ("P1", "As the Court held in Trump v. United States, 603 U.S. 593 (2024), the immunity is absolute."))
    assert pipeline.answer("summarize the first passage", NoSearch(), INDEX, ON, previous=turn)["shown_sentences"]


@pytest.mark.parametrize("section, opinion_label, shown", [
    ("Part II", "Dissenting opinion (Scalia)", "Dissenting opinion (Scalia) - Part II"),     # Rasul, run 1
    ("Part C", "Majority opinion (Roberts)", "Majority opinion (Roberts) - Part C"),         # Shelby County, run 1
    ("Ginsburg, J., dissenting - Part IV", "Concurring opinion (Thomas)", "Ginsburg, J., dissenting - Part IV"),
    ("Opinion of the Court (Kagan)", "Majority opinion", "Opinion of the Court (Kagan)"),
    ("Syllabus", "Syllabus", "Syllabus"),
    ("", "Dissenting opinion (Alito)", "Dissenting opinion (Alito)"),
])
def test_the_label_says_who_is_speaking(section, opinion_label, shown):
    assert pipeline.label_of({"section": section, "opinion_label": opinion_label}) == shown


# ---------- before run 3 (EVALUATION.md: S003 showed Riley's docket line and facts, S014 showed "*803") ----------
RILEY = {**MAJORITY, "section": "Syllabus", "opinion_label": "Syllabus", "is_syllabus": True,
         "text": "No. 13-132. Argued April 29, 2014-Decided June 25, 2014 In No. 13-132, petitioner Riley was stopped for a "
                 "traffic violation. Held: The police generally may not, without a warrant, search digital information on "
                 "a cell phone seized from an individual who has been arrested. The *803 Act's restrictions are wildly "
                 "underinclusive when judged against its asserted justification."}
TURN_RILEY = json.loads(json.dumps({"question": "q", "sentences": [], "passages": [["P1", RILEY]]}))


@pytest.mark.parametrize("docket", [
    "No. 13-132. Argued April 29, 2014-Decided June 25, 2014 In No. 13-132, petitioner Riley was stopped",
    "Argued April 29, 2014-Decided June 25, 2014 In No. 13-132",
])
def test_a_docket_or_argument_line_is_removed(monkeypatch, docket):
    picks(monkeypatch, ("P1", docket))
    r = pipeline.answer("explain the first passage", NoSearch(), INDEX, ON, previous=TURN_RILEY)
    assert not r["shown_sentences"] and r["removed"][0]["problems"] == ["a docket or argument line, not the passage's point"]


def test_the_holding_is_kept(monkeypatch):
    picks(monkeypatch, ("P1", "Held: The police generally may not, without a warrant, search digital information"))
    assert pipeline.answer("explain the first passage", NoSearch(), INDEX, ON, previous=TURN_RILEY)["shown_sentences"]


def test_page_markers_are_left_out_of_the_shown_words(monkeypatch):
    picks(monkeypatch, ("P1", "The *803 Act's restrictions are wildly underinclusive"))
    (shown,) = pipeline.answer("explain the first passage", NoSearch(), INDEX, ON, previous=TURN_RILEY)["shown_sentences"]
    assert "*803" not in shown["text"] and "The Act's restrictions are wildly underinclusive" in shown["text"]


def test_the_picker_prefers_the_holding_over_facts_and_procedure(monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "_ask_json", lambda system, user, *a, **k: calls.append(system) or {"picks": []})
    llm.pick_sentences("explain the first passage", {"P1": RILEY})
    assert "Held:" in calls[0] and "procedural history" in calls[0] and "docket" in calls[0]


# ---------- before run 5 (EVALUATION.md: run 4, S007 picks in quotation marks, S003 docket glued to a fact) ----------
@pytest.mark.parametrize("wrapped", [
    "“The President enjoys absolute immunity for actions within his conclusive”",
    '"The President enjoys absolute immunity for actions within his conclusive"',
    "'The President enjoys absolute immunity for actions within his conclusive'",
])
def test_quotation_marks_around_a_whole_pick_are_not_part_of_it(monkeypatch, wrapped):
    picks(monkeypatch, ("P1", wrapped))
    (shown,) = pipeline.answer("summarize the first passage", NoSearch(), INDEX, ON, previous=TURN)["shown_sentences"]
    assert shown["text"] == ("Opinion of the Court (Roberts): “The President enjoys absolute immunity for actions "
                             "within his conclusive”")


def test_a_docket_line_glued_to_a_fact_is_cut_off_and_the_fact_kept(monkeypatch):
    picks(monkeypatch, ("P1", "No. 13-132. Argued April 29, 2014-Decided June 25, 2014 In No. 13-132, petitioner Riley "
                              "was stopped for a traffic violation."))
    (shown,) = pipeline.answer("explain the first passage", NoSearch(), INDEX, ON, previous=TURN_RILEY)["shown_sentences"]
    assert shown["text"].endswith("“In No. 13-132, petitioner Riley was stopped for a traffic violation.”")


def test_a_pick_that_is_only_a_docket_line_is_still_removed(monkeypatch):
    picks(monkeypatch, ("P1", "No. 13-132. Argued April 29, 2014-Decided June 25, 2014"))
    r = pipeline.answer("explain the first passage", NoSearch(), INDEX, ON, previous=TURN_RILEY)
    assert not r["shown_sentences"] and r["removed"][0]["problems"] == ["a docket or argument line, not the passage's point"]
