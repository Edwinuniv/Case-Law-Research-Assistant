"""Run all test questions from the terminal (the admin page does the same).
Usage: python -m scripts.run_eval "note about this run"   -> TUNE split only: metrics and the tau sweep
       python -m scripts.run_eval --test RUN_ID           -> TEST split, ONCE, after tau_abstain is chosen
Not the guide's version: it printed both splits after every run, but EVALUATION.md chooses tau on the
TUNE split without looking at the TEST split (SR29)."""
import sys
from app import db, evaluate
from app.citations import CitationIndex
from app.search import Searcher


def report(pairs, s, split):
    print(f"\n== {split} split ==")
    for k, v in evaluate.metrics(pairs, s, split).items():
        print(f"  {k:32} {v}")
    if split == "tune":                                  # the table used to choose tau_abstain (EVALUATION.md)
        print("\n  tau    precision  recall  wrong abstentions  wrong answers")
        for row in evaluate.sweep(pairs, s, "tune"):
            print(f"  {row['tau']:.2f}   {row['precision']!s:9}  {row['recall']!s:6}  "
                  f"{row['wrong_abstentions']:17}  {row['wrong_answers']}")


def main(argv, s=None):
    s = s or db.get_settings()
    if argv[:1] == ["--test"]:
        run_id = int(argv[1])
        print(f"TEST split of run {run_id}, with tau_abstain = {s['tau_abstain']} (report it once, unchanged)")
        report(evaluate.load_run(run_id), s, "test")
    else:
        run_id = evaluate.run_evaluation(Searcher(), CitationIndex(), "command line", " ".join(argv))
        report(evaluate.load_run(run_id), s, "tune")
        print(f"\nSaved as run {run_id}: open /admin/eval/{run_id}")


if __name__ == "__main__":
    main(sys.argv[1:])
