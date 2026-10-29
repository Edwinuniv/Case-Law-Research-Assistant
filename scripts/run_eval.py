"""Run all test questions from the terminal (the admin page does the same).
Usage: python -m scripts.run_eval "note about this run" """
import sys
from app import db, evaluate
from app.citations import CitationIndex
from app.search import Searcher

run_id = evaluate.run_evaluation(Searcher(), CitationIndex(), "command line", " ".join(sys.argv[1:]))
s = db.get_settings()
pairs = evaluate.load_run(run_id)
for split in ("tune", "test"):
    print(f"\n== {split} split ==")
    for k, v in evaluate.metrics(pairs, s, split).items():
        print(f"  {k:32} {v}")
print(f"\nSaved as run {run_id}: open /admin/eval/{run_id}")
