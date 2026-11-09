"""Defence: the online database has no evaluation run (the dump was made before run 2), so the admin pages Runs,
Compare and Threshold preview are empty. A run saved in eval/runs is loaded into the database as it was.
Written from the expected behaviour, before the code."""
import json
import pytest
from app.config import DEFAULT_SETTINGS
from tests.test_evaluate import res

SETTINGS = dict(DEFAULT_SETTINGS, tau_abstain=0.2)


def saved_file(tmp_path, name="eval_run2.json"):
    path = tmp_path / name
    path.write_text(json.dumps({
        "run_id": 1, "created_at": "2026-11-08T13:05:00+00:00", "trigger": "command line", "status": "done",
        "note": "run 2", "settings": SETTINGS, "data": {"decisions": 2415},
        "results": [{"question_id": "a", "tag": "answerable", "split": "tune", "result": res(0.9)},
                    {"question_id": "u", "tag": "unanswerable", "split": "test", "result": res(0.1)}]}))
    return path


def test_an_imported_run_reads_back_like_its_file(clean_db, tmp_path):
    from app import evaluate
    from scripts.import_run import import_run
    path = saved_file(tmp_path)
    run_id = import_run(path)
    assert evaluate.load_run(run_id) == evaluate.load_run_file(path)
    with clean_db.connect() as con:
        run = con.execute("SELECT * FROM eval_runs WHERE id = %s", (run_id,)).fetchone()
    assert run["status"] == "done" and run["settings"] == SETTINGS                 # the run's own settings
    assert run["created_at"].isoformat().startswith("2026-11-08T13:05")            # its own date, not today
    assert "eval_run2.json" in run["note"] and "run 2" in run["note"]


def test_the_same_file_is_not_imported_twice(clean_db, tmp_path):
    from scripts.import_run import import_run
    path = saved_file(tmp_path)
    import_run(path)
    with pytest.raises(SystemExit, match="already imported"):
        import_run(path)
    with clean_db.connect() as con:
        assert con.execute("SELECT count(*) FROM eval_runs").fetchone()["count"] == 1


def test_two_different_files_are_two_runs(clean_db, tmp_path):
    from scripts.import_run import import_run
    assert import_run(saved_file(tmp_path, "eval_run1.json")) != import_run(saved_file(tmp_path, "eval_run2.json"))
