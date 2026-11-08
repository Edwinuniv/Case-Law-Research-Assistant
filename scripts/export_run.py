"""WEEK 8, step 8.2 - Save a run from the database to eval/runs/eval_<name>.json (results, settings, data,
TUNE metrics and tau sweep with the run's own settings). A restore of the database empties eval_runs:
run 1 survived only because it had been saved by hand. Run it after each resume; the file is replaced.
No TEST numbers are saved (SR29: TEST is reported once, with run_eval --test).
Usage: python -m scripts.export_run RUN_ID NAME "which dump"
       e.g. python -m scripts.export_run 1 run2 "Yasser's dump of 2026-11-06 21:20 UTC minus 8 out-of-scope" """
import sys
import json
from app import config, db, evaluate


def main(argv):
    run_id, name, dump = int(argv[0]), argv[1], " ".join(argv[2:])
    with db.connect() as con:
        run = con.execute("SELECT * FROM eval_runs WHERE id = %s", (run_id,)).fetchone()
        results = con.execute("SELECT question_id, tag, split, result FROM eval_results WHERE run_id = %s "
                              "ORDER BY question_id", (run_id,)).fetchall()
        data = {"decisions": con.execute("SELECT count(*) FROM decisions").fetchone()["count"],
                "chunks": con.execute("SELECT count(*) FROM chunks").fetchone()["count"], "dump": dump}
    pairs = evaluate.load_run(run_id)
    saved = {"run_id": run_id, "created_at": run["created_at"].isoformat(), "trigger": run["trigger"],
             "status": run["status"], "note": run["note"], "settings": run["settings"], "data": data,
             "tune_metrics": evaluate.metrics(pairs, run["settings"], "tune"),
             "tune_sweep": evaluate.sweep(pairs, run["settings"], "tune"), "results": results}
    (config.EVAL_DIR / "runs").mkdir(exist_ok=True)
    out = config.EVAL_DIR / "runs" / f"eval_{name}.json"
    json.dump(saved, open(out, "w"), indent=1)
    print(f"Run {run_id} ({run['status']}, {len(results)} questions) saved in {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
