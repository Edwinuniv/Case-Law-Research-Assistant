"""The admin pages open on the TUNE split (Edwin's request for Week 8).
Expected behaviour, written before the code, from EVALUATION.md: "On the TUNE split (80%), choose the
tau_abstain ... Then report the TEST split (20%) once, without changing tau" and SR29 (thresholds tuned on
part of the test set, final results reported on the other 20%). So after a run, an admin who opens the
overview, the list of runs, a run, the compare page or the threshold preview must see TUNE numbers, never
TEST numbers by accident. TEST must still be reachable when asked for, for the one final report.
The run has 2 answerable TUNE questions and 1 answerable TEST question, so "answerable" tells which split
the numbers come from. Fake search and fake model; TEST database."""
import pytest
from app import evaluate, llm
from tests.test_api_admin import c, csrf, log_in          # noqa: F401 (c is the fixture)
from tests.test_api_research import FakeSearcher, good_model
from tests.test_citations import INDEX


@pytest.fixture
def run_id(c, clean_db, monkeypatch):
    monkeypatch.setattr(llm, "ask_model", good_model)
    with clean_db.connect() as con:
        for qid, split in [("A001", "tune"), ("A002", "tune"), ("A003", "test")]:
            con.execute("INSERT INTO test_questions (id, tag, split, question, gold_decision_ids) "
                        "VALUES (%s, 'answerable', %s, 'Is the President immune from prosecution?', '{9987186}')",
                        (qid, split))
    run = evaluate.run_evaluation(FakeSearcher(), INDEX, "manual", "fake run", judge=False, log=lambda *a: None)
    log_in(c, "boss@example.com")
    return run


def test_overview_shows_the_tune_split(c, run_id):
    assert c.get("/api/admin/home").json()["metrics"]["answerable"] == 2


def test_list_of_runs_shows_the_tune_split(c, run_id):
    assert c.get("/api/admin/eval").json()[0]["metrics"]["answerable"] == 2


def test_run_page_opens_on_tune_and_test_stays_reachable(c, run_id):
    d = c.get(f"/api/admin/eval/{run_id}").json()
    assert d["split"] == "tune" and d["metrics"]["answerable"] == 2
    d = c.get(f"/api/admin/eval/{run_id}", params={"split": "test"}).json()    # the one final report
    assert d["split"] == "test" and d["metrics"]["answerable"] == 1


def test_compare_opens_on_tune(c, run_id):
    d = c.get("/api/admin/eval/compare", params={"a": run_id, "b": run_id}).json()
    assert d["split"] == "tune"
    assert next(r for r in d["rows"] if r["metric"] == "answerable")["b"] == 2


def test_threshold_preview_uses_tune(c, run_id):                    # FR23: thresholds are chosen here
    d = c.get("/api/admin/settings/preview",
              params={"tau_abstain": 0.5, "tau_confident": 0.6, "min_retrieval": 0.3}).json()
    assert d["split"] == "tune"
