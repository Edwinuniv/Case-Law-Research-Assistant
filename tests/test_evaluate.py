import pytest
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
                                  alias={9987186: 9987186}, decisions={})
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

def test_judge_waits_on_rate_limit_but_not_on_other_errors(monkeypatch):
    from app import evaluate, llm
    waits = []
    monkeypatch.setattr(evaluate.time, "sleep", waits.append)
    replies = [llm.ModelError("rate limit reached, retry after 2 s"), "yes"]
    def judge(statement, text):
        r = replies.pop(0)
        if isinstance(r, Exception): raise r
        return r
    monkeypatch.setattr(llm, "judge_support", judge)
    assert evaluate.judge_with_retry("s", "p", log=lambda m: None) == "yes" and waits == [3.0]
    def timeout(statement, text): raise llm.ModelError("timeout after 30 seconds")
    monkeypatch.setattr(llm, "judge_support", timeout)
    assert evaluate.judge_with_retry("s", "p", log=lambda m: None) == "error" and waits == [3.0]


# --- Week 8: the TEST split is reported once, after tau is chosen on TUNE (EVALUATION.md, SR29) ---
def fake_run(monkeypatch):
    import scripts.run_eval as run_eval
    pairs = [({**q("a", "answerable"), "split": "tune"}, res(0.9)), (q("b", "answerable"), res(0.2))]
    monkeypatch.setattr(run_eval, "Searcher", lambda: None)
    monkeypatch.setattr(run_eval, "CitationIndex", lambda: None)
    monkeypatch.setattr(run_eval.evaluate, "run_evaluation", lambda *a, **kw: 7)
    monkeypatch.setattr(run_eval.evaluate, "load_run", lambda run_id: pairs)
    monkeypatch.setattr(run_eval.evaluate, "run_status", lambda run_id: "done")
    return run_eval

def test_a_run_shows_only_the_tune_split_and_the_sweep(monkeypatch, capsys):
    fake_run(monkeypatch).main(["week 8"], S)
    out = capsys.readouterr().out
    assert "== tune split ==" in out and "test split" not in out.lower()
    assert "answerable                       1" in out          # only the tune question is counted
    assert "tau    precision" in out                             # the sweep, to choose tau_abstain

def test_the_test_split_is_shown_only_when_asked(monkeypatch, capsys):
    fake_run(monkeypatch).main(["--test", "7"], S)
    out = capsys.readouterr().out
    assert "== test split ==" in out and "== tune split ==" not in out
    assert "answerable                       1" in out          # only the test question is counted


# --- Week 8: Groq's free tier allows 200,000 tokens per day; a full run needs about 500,000,
#     so a run pauses at the daily limit and is resumed later (--resume), as ONE run ---
DAILY = ("ERROR", "language model failed: rate limit reached per day, retry after 1320 s")
OK = ("NOT_SUPPORTED", "the model said the passages do not answer this")

def scripted_run(clean_db, monkeypatch, replies, seen_settings):
    from app import evaluate
    with clean_db.connect() as con:
        for i in ("U1", "U2", "U3"):
            con.execute("INSERT INTO test_questions (id, tag, split, question) VALUES (%s, 'unanswerable', 'tune', 'q?')", (i,))
    def fake_answer(question, searcher, index, settings, skip_gate=False):
        seen_settings.append(settings)
        status, reason = replies.pop(0)
        return {"question": question, "status": status, "reason": reason, "sentences": [], "removed": [],
                "passages": [], "top_score": 0.9, "support_score": 0.0, "fabrications_caught": 0,
                "retrieved_decisions": [], "model_said": None, "ms_total": 1}
    monkeypatch.setattr(evaluate, "answer", fake_answer)
    monkeypatch.setattr(evaluate.time, "sleep", lambda seconds: None)
    return evaluate

def test_daily_limit_pauses_the_run_without_saving_an_error(clean_db, monkeypatch):
    evaluate = scripted_run(clean_db, monkeypatch, [OK, DAILY], [])
    run_id = evaluate.run_evaluation(object(), CHECK_INDEX, log=lambda m: None)
    assert evaluate.run_status(run_id) == "paused"
    assert [q["id"] for q, _ in evaluate.load_run(run_id)] == ["U1"]          # U2 is not saved as an ERROR

def test_resume_finishes_the_same_run_with_its_own_settings(clean_db, monkeypatch):
    seen = []
    evaluate = scripted_run(clean_db, monkeypatch, [OK, DAILY, OK, OK], seen)
    run_id = evaluate.run_evaluation(object(), CHECK_INDEX, log=lambda m: None)
    assert evaluate.run_evaluation(object(), CHECK_INDEX, log=lambda m: None, resume=run_id) == run_id
    assert evaluate.run_status(run_id) == "done"
    assert [q["id"] for q, _ in evaluate.load_run(run_id)] == ["U1", "U2", "U3"]   # U1 not asked twice
    assert len(seen) == 4 and all(s == seen[0] for s in seen)

def test_resume_refuses_if_the_settings_changed(clean_db, monkeypatch):
    evaluate = scripted_run(clean_db, monkeypatch, [OK, DAILY], [])
    run_id = evaluate.run_evaluation(object(), CHECK_INDEX, log=lambda m: None)
    with clean_db.connect() as con:
        con.execute("INSERT INTO settings (key, value) VALUES ('tau_abstain', '0.4') "
                    "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value")
    with pytest.raises(ValueError, match="tau_abstain"):
        evaluate.run_evaluation(object(), CHECK_INDEX, log=lambda m: None, resume=run_id)

def test_daily_limit_during_the_judge_also_pauses(monkeypatch):
    from app import evaluate, llm
    monkeypatch.setattr(evaluate.time, "sleep", lambda seconds: None)     # never really wait in a test
    def judge(statement, text):
        raise llm.ModelError("rate limit reached per day, retry after 600 s")
    monkeypatch.setattr(llm, "judge_support", judge)
    with pytest.raises(evaluate.DailyLimit):
        evaluate.judge_with_retry("s", "p", log=lambda m: None)

def test_a_paused_run_says_how_to_resume_and_shows_no_metrics(monkeypatch, capsys):
    run_eval = fake_run(monkeypatch)
    monkeypatch.setattr(run_eval.evaluate, "run_status", lambda run_id: "paused")
    run_eval.main(["--resume", "7"], S)
    out = capsys.readouterr().out
    assert "--resume 7" in out and "split ==" not in out



# --- Step 8.3: the checker gave false alarms on real citations (Boumediene in run 1; 88 of 2,006 decisions) ---
from tests.test_citations import BOUMEDIENE

def add_decision_with(clean_db, decision_id, citations):
    with clean_db.connect() as con:
        con.execute("INSERT INTO decisions (decision_id, all_cluster_ids, case_name, date_filed, citations, licence) "
                    "VALUES (%s, %s, 'X v. Y', '2008-06-12', %s, 'test')", (decision_id, [decision_id], citations))

def checked_for(decision_id, index):
    r = {"passages": [("P1", {**TRUMP, "decision_id": decision_id})], "sentences": [{"text": "Text.", "sources": ["P1"]}]}
    return check_shown_citations(r, {"must_not_appear": []}, index)

def test_checker_accepts_a_real_citation_shared_by_two_copies_of_a_decision(clean_db):   # SR38 (a)
    add_decision_with(clean_db, 145795, ["128 S. Ct. 2229"])        # Boumediene; its copy 145943 has the same citation
    assert checked_for(145795, BOUMEDIENE) == ([[]], 1)

def test_checker_checks_the_citation_the_page_shows(clean_db):                         # SR38 (a), Joe's #58
    add_decision_with(clean_db, 145795, ["0 Cal. Daily Op. Serv. 3128", "553 U.S. 723"])
    index = StaticCitationIndex(citations={"553 U.S. 723": 145795}, alias={145795: 145795}, decisions={})
    assert checked_for(145795, index) == ([[]], 1)                  # 553 U.S. 723 is shown and checked


# --- Step 8.2: run 1 (saved file) against run 2 (database), on the questions both runs answered ---
import json

def tune(i, tag="answerable"):
    return {**q(i, tag), "split": "tune"}

def test_a_saved_run_file_is_read_like_a_run_from_the_database(tmp_path, monkeypatch):
    from app import evaluate
    monkeypatch.setattr(evaluate, "load_questions", lambda: [tune("a")])
    path = tmp_path / "run.json"
    path.write_text(json.dumps({"run_id": 1, "results": [{"question_id": "a", "tag": "answerable", "split": "tune",
                                                           "result": res(0.9)}]}))
    assert evaluate.load_run_file(path) == [(tune("a"), res(0.9))]

def test_only_questions_answered_in_both_runs_are_compared():
    from app.evaluate import same_questions
    a = [(tune("x"), res(0.9)), (tune("y"), res(0.9))]
    b = [(tune("y"), res(0.2)), (tune("z"), res(0.2))]
    pa, pb = same_questions(a, b)
    assert [x["id"] for x, _ in pa] == ["y"] and [x["id"] for x, _ in pb] == ["y"]

def compare_runs_main(monkeypatch, tmp_path, run_a, run_b):
    from scripts import compare_runs
    monkeypatch.setattr(compare_runs.evaluate, "load_run_file", lambda path: run_a)
    monkeypatch.setattr(compare_runs.evaluate, "load_run", lambda run_id: run_b)
    monkeypatch.setattr(compare_runs.config, "EVAL_DIR", tmp_path)
    compare_runs.main(["eval/runs/run1.json", "1"], S)
    saved, = (tmp_path / "runs").glob("compare_*.json")
    return json.loads(saved.read_text())

def test_compare_runs_uses_common_tune_questions_and_saves_the_numbers(monkeypatch, tmp_path, capsys):
    run_a = [(tune("a"), res(0.9)), (tune("b"), res(0.9))]                      # b: not asked yet in run 2
    run_b = [(tune("a"), res(0.2)), (q("t", "answerable"), res(0.9))]          # t: TEST split, never compared
    saved = compare_runs_main(monkeypatch, tmp_path, run_a, run_b)
    rows = {r["metric"]: r for r in saved["rows"]}
    assert saved["questions"] == ["a"] and rows["answerable"]["a"] == 1 and rows["answerable"]["b"] == 1
    assert rows["abstained_but_should_answer"]["worse"]
    assert saved["flips"][0]["id"] == "a" and "1 question" in capsys.readouterr().out


# --- Step 8.2: a run is saved to eval/runs so a restore of the database cannot erase it (run 1 did) ---
from psycopg.types.json import Jsonb

def saved_run(clean_db, monkeypatch, tmp_path):
    from scripts import export_run
    with clean_db.connect() as con:
        con.execute("INSERT INTO test_questions (id, tag, split, question, gold_decision_ids) VALUES "
                    "('a', 'answerable', 'tune', 'q?', '{1}'), ('u', 'unanswerable', 'tune', 'q?', '{}')")
        run_id = con.execute("INSERT INTO eval_runs (trigger, status, settings, note) VALUES "
                             "('command line', 'paused', %s, 'run 2') RETURNING id", (Jsonb(S),)).fetchone()["id"]
        for qid, tag, support in (("a", "answerable", 0.9), ("u", "unanswerable", 0.2)):
            con.execute("INSERT INTO eval_results (run_id, question_id, tag, split, result) VALUES (%s, %s, %s, 'tune', %s)",
                        (run_id, qid, tag, Jsonb(res(support))))
    monkeypatch.setattr(export_run.config, "EVAL_DIR", tmp_path)
    export_run.main([str(run_id), "run2", "dump of 2026-11-06"])
    return run_id, tmp_path / "runs" / "eval_run2.json"

def test_an_exported_run_reads_back_like_the_database_run(clean_db, monkeypatch, tmp_path):
    from app import evaluate
    run_id, path = saved_run(clean_db, monkeypatch, tmp_path)
    saved = json.loads(path.read_text())
    assert saved["run_id"] == run_id and saved["status"] == "paused" and saved["settings"] == S
    assert saved["data"]["dump"] == "dump of 2026-11-06" and "decisions" in saved["data"]
    assert evaluate.load_run_file(path) == evaluate.load_run(run_id)

def test_an_exported_run_keeps_the_tune_metrics_and_sweep_of_its_own_settings(clean_db, monkeypatch, tmp_path):
    from app import evaluate
    run_id, path = saved_run(clean_db, monkeypatch, tmp_path)
    saved = json.loads(path.read_text())
    assert saved["tune_metrics"] == evaluate.metrics(evaluate.load_run(run_id), S, "tune")
    assert saved["tune_sweep"] == evaluate.sweep(evaluate.load_run(run_id), S, "tune")
    assert "test" not in json.dumps(saved["tune_metrics"]) and not any("test" in k for k in saved)   # SR29: no TEST numbers
