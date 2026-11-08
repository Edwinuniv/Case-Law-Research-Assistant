"""WEEK 8, step 8.2 - Compare two runs on the TUNE questions BOTH answered (plus adversarial, as the metrics).
A run is a database run id or a saved file in eval/runs/ (run 1 lives only in its file: a restore empties
eval_runs). Run 1 paused after 39 questions, so the questions only one run has are left out.
The result is saved in eval/runs/compare_<date>.json: the report quotes that file (every number from a saved run).
Usage: python -m scripts.compare_runs eval/runs/eval_run1_before_text_fixes_2026-11-06.json 1"""
import sys
import json
import datetime
from app import config, db, evaluate
from scripts.show_citations import keep_split


def load(run):
    return evaluate.load_run_file(run) if run.endswith(".json") else evaluate.load_run(int(run))


def main(argv, s=None):
    s = s or db.get_settings()
    pa, pb = evaluate.same_questions(keep_split(load(argv[0]), "tune"), keep_split(load(argv[1]), "tune"))
    rows, flips = evaluate.compare_pairs(pa, pb, s, "tune")
    n = len(pb)
    print(f"A = {argv[0]}\nB = {argv[1]}\n{n} question{'s' * (n != 1)} in both runs (TUNE + adversarial), "
          f"tau_abstain {s['tau_abstain']}\n")
    print(f"  {'metric':32} {'A':>10} {'B':>10}")
    for r in rows:
        print(f"  {r['metric']:32} {r['a']!s:>10} {r['b']!s:>10}{'   <- worse' if r['worse'] else ''}")
    print(f"\n== Questions whose status changed: {len(flips)} ==")
    for f in flips:
        print(f"  {f['id']} ({f['tag']}): {f['a']} -> {f['b']}")

    date = datetime.datetime.now().isoformat(timespec="seconds")
    (config.EVAL_DIR / "runs").mkdir(exist_ok=True)
    out = config.EVAL_DIR / "runs" / f"compare_{date.replace(':', '-')}.json"
    json.dump({"date": date, "a": argv[0], "b": argv[1], "split": "tune", "tau_abstain": s["tau_abstain"],
               "questions": [q["id"] for q, _ in pb], "rows": rows, "flips": flips}, open(out, "w"), indent=1)
    print(f"\nsaved {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
