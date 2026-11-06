"""Merge copies of one decision that CourtListener stores twice (e.g. Bruen: 6480696 and 7686272).
Copies = same case name, dates at most 60 days apart, opinion texts at least 80% identical.
The kept decision is the copy with the most text; the others become aliases (cluster_alias), and
their opinions and chunks are deleted, so no embeddings have to be recomputed.
Usage: python -m scripts.merge_duplicates            (dry run: shows every same-name pair)
       python -m scripts.merge_duplicates --apply    (merges)
A fresh load (seed --corpus) does this automatically."""
import sys
from app import db, ingest

with db.connect() as con:
    groups, pairs = ingest.find_duplicate_decisions(con)
for a, b, name, da, dbb, sim, copy in sorted(pairs, key=lambda p: p[3]):
    print(f"{'COPY ' if copy else 'apart'} {sim:5.2f}  {a} ({da}) / {b} ({dbb})  {name[:55]}")
print(f"\n{len(pairs)} same-name pairs within 60 days; {len(groups)} groups of copies:")
for kept, merged in groups:
    print(f"  keep {kept}, merge {merged}")
if "--apply" in sys.argv:
    ingest.merge_duplicate_decisions()
    print("Test questions whose gold_decision_ids name a merged id still count (the evaluation "
          "follows cluster_alias); better to replace them with the kept id.")
else:
    print("\nDry run: nothing changed. Run again with --apply to merge.")
