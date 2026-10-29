from app.evaluate import status_at, metrics
from app.config import DEFAULT_SETTINGS

S = dict(DEFAULT_SETTINGS)

def res(support, top=0.8, said="SUPPORTED", kept=1, ranked=(1,), false=()):
    return {"status_raw": "ANSWERED", "top_score": top, "model_said": said, "support_score": support,
            "n_kept": kept, "ranked_decisions": list(ranked), "false_by_sentence": [list(false)] * kept,
            "citations_shown": kept, "fabrications_caught": 0, "judgements": ["yes"] * kept,
            "sentences": [{"groundedness": 1.0}] * kept, "ms_total": 100}

def q(i, tag, gold=(1,)):
    return {"id": i, "tag": tag, "split": "test", "question": "?", "gold_decision_ids": list(gold), "must_not_appear": []}

def test_status_follows_thresholds():
    assert status_at(res(0.9), S) == "ANSWERED"
    assert status_at(res(0.6), S) == "LOW_CONFIDENCE"
    assert status_at(res(0.3), S) == "NOT_SUPPORTED"
    assert status_at(res(0.9, top=0.1), S) == "NOT_SUPPORTED"

def test_abstention_precision_and_recall():
    pairs = [(q("a", "answerable"), res(0.9)), (q("b", "unanswerable"), res(0.2)),
             (q("c", "unanswerable"), res(0.9)), (q("d", "answerable"), res(0.2))]
    m = metrics(pairs, S)
    assert m["abstention_precision"] == 0.5 and m["abstention_recall"] == 0.5

def test_false_citations_count_only_when_shown():
    pairs = [(q("a", "adversarial"), res(0.9, false=("x",))), (q("b", "adversarial"), res(0.1, false=("y",)))]
    assert metrics(pairs, S)["false_citations_shown"] == 1

def test_recall_at_k():
    pairs = [(q("a", "answerable", gold=(5,)), res(0.9, ranked=(1, 2, 5)))]
    m = metrics(pairs, S)
    assert m["recall@1"] == 0 and m["recall@5"] == 1 and round(m["mrr@10"], 2) == 0.33


# --- Not in the guide: tests for gaps found by breaking the code on purpose (see AI_LOG.md) ---
from app.evaluate import check_shown_citations
from app.citations import StaticCitationIndex

CHECK_INDEX = StaticCitationIndex(citations={"603 U.S. 593": 9987186, "467 U.S. 837": 111, "500 U.S. 1": 222},
                                  alias={9987186: 9987186}, case_names=[])
TRUMP = {"decision_id": 9987186, "opinion_id": 1, "text": "..."}

def add_decision(clean_db, decision_id, citation):
    with clean_db.connect() as con:
        con.execute("INSERT INTO decisions (decision_id, all_cluster_ids, case_name, date_filed, citations, licence) "
                    "VALUES (%s, %s, 'X v. Y', '2024-07-01', %s, 'test')", (decision_id, [decision_id], [citation]))

def checked(text, passage=TRUMP, must_not_appear=()):
    r = {"passages": [("P1", passage)], "sentences": [{"text": text, "sources": ["P1"]}]}
    problems, _ = check_shown_citations(r, {"must_not_appear": list(must_not_appear)}, CHECK_INDEX)
    return problems[0]

def test_checker_flags_a_rendered_citation_of_another_case(clean_db):      # SR38 (a)
    add_decision(clean_db, 5555, "467 U.S. 837")        # decision 5555 stores Chevron's citation
    assert any("rendered citation" in p for p in checked("Text.", passage={**TRUMP, "decision_id": 5555}))

def test_checker_allows_a_citation_from_the_citation_map(clean_db):        # SR38 (b)
    add_decision(clean_db, 9987186, "603 U.S. 593")
    with clean_db.connect() as con:
        con.execute("INSERT INTO citation_map (citing_opinion_id, cited_opinion_id, cited_cluster_id, depth) "
                    "VALUES (1, 2, 111, 1)")
    assert checked("The opinion relied on 467 U.S. 837.") == []

def test_checker_flags_a_real_citation_from_nowhere(clean_db):             # SR38 (b)
    add_decision(clean_db, 9987186, "603 U.S. 593")
    assert any("not from a retrieved opinion" in p for p in checked("Compare 500 U.S. 1."))

def test_checker_flags_forbidden_text(clean_db):                           # SR38 (c)
    add_decision(clean_db, 9987186, "603 U.S. 593")
    assert checked("Halvorsen held so.", must_not_appear=["halvorsen"]) == ["forbidden text shown: halvorsen"]

def test_split_keeps_only_that_split_plus_adversarial():                    # SR29
    tune = {**q("t", "answerable"), "split": "tune"}
    pairs = [(tune, res(0.9)), (q("s", "answerable"), res(0.9)), ({**q("x", "adversarial"), "split": "tune"}, res(0.1))]
    m = metrics(pairs, S, split="test")
    assert m["answerable"] == 1 and m["adversarial"] == 1

def test_sweep_moves_with_the_threshold():                                  # SR29
    from app.evaluate import sweep
    pairs = [({**q("a", "answerable"), "split": "tune"}, res(0.6)), ({**q("u", "unanswerable"), "split": "tune"}, res(0.4))]
    rows = {row["tau"]: row for row in sweep(pairs, S)}
    assert rows[0.3]["wrong_answers"] == 1 and rows[0.3]["wrong_abstentions"] == 0   # both answered
    assert rows[0.5]["wrong_answers"] == 0 and rows[0.5]["wrong_abstentions"] == 0   # the right split
    assert rows[0.7]["wrong_abstentions"] == 1                                        # both abstain

def test_compare_flags_worse_and_lists_flips(monkeypatch):                  # FR19, SR40
    from app import evaluate
    runs = {1: [(q("a", "answerable"), res(0.9))], 2: [(q("a", "answerable"), res(0.2))]}
    monkeypatch.setattr(evaluate, "load_run", lambda run_id: runs[run_id])
    rows, flips = evaluate.compare(1, 2, S)
    worse = {r["metric"] for r in rows if r["worse"]}
    assert "abstained_but_should_answer" in worse
    assert flips == [{"id": "a", "question": "?", "tag": "answerable", "a": "ANSWERED", "b": "NOT_SUPPORTED"}]

def test_evaluation_waits_and_retries_after_a_rate_limit(clean_db, monkeypatch):
    from app import evaluate
    with clean_db.connect() as con:
        con.execute("INSERT INTO test_questions (id, tag, split, question) VALUES ('U1', 'unanswerable', 'test', 'q?')")
    replies = [{"status": "ERROR", "reason": "language model failed: rate limit reached, retry after 3 s"},
               {"status": "NOT_SUPPORTED", "reason": "the model said the passages do not answer this"}]
    def fake_answer(question, searcher, index, settings, skip_gate=False):
        reply = replies.pop(0)
        return {"question": question, "status": reply["status"], "reason": reply["reason"], "sentences": [], "removed": [],
                "passages": [], "top_score": 0.9, "support_score": 0.0, "fabrications_caught": 0,
                "retrieved_decisions": [], "model_said": None, "ms_total": 1}
    waits = []
    monkeypatch.setattr(evaluate, "answer", fake_answer)
    monkeypatch.setattr(evaluate.time, "sleep", waits.append)
    run_id = evaluate.run_evaluation(object(), CHECK_INDEX, log=lambda m: None)
    (_, result), = evaluate.load_run(run_id)
    assert result["status_raw"] == "NOT_SUPPORTED" and waits and waits[0] >= 3
