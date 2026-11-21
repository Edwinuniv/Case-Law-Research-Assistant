"""Give the citation-map rows of the opinion copies we skipped to our opinion with the same text (SPEC 11, 2026-11-21).
CourtListener often stores one opinion twice (Harvard XML and HTML with citations). Step 1.8 keeps one copy; the
citation map mostly hangs on the other one (e.g. Shelby County: our 9515886 had no row, its copy 931614 had them).
Only citation_map changes: rows are added, none removed, a row already there is not added twice. No re-index.
Needs data/work/opinions.jsonl and opinion_cluster_pairs.csv (step 1.5).
Usage: python -m scripts.remap_citation_map            (dry run: what would change)
       python -m scripts.remap_citation_map --apply    (writes, and saves the report)"""
import json
import sys
from collections import Counter, defaultdict
import numpy as np
from app import config, db
from app.chunking import pick_text
from app.ingest import copy_targets, rows_to_add, shingles

SHELBY = 9515886
apply = "--apply" in sys.argv

pairs = dict(np.loadtxt(config.WORK / "opinion_cluster_pairs.csv", delimiter=",", dtype=np.int64, ndmin=2))
with db.connect() as con:
    alias = {r["cluster_id"]: r["decision_id"] for r in con.execute("SELECT cluster_id, decision_id FROM cluster_alias")}
    alias.update({r["decision_id"]: r["decision_id"] for r in con.execute("SELECT decision_id FROM decisions")})
    copies = [r["citing_opinion_id"] for r in con.execute(
        """SELECT DISTINCT citing_opinion_id FROM citation_map m
           WHERE NOT EXISTS (SELECT 1 FROM opinions o WHERE o.opinion_id = m.citing_opinion_id)""")]
    decision_of = {c: alias.get(int(pairs.get(c, -1))) for c in copies}
    decisions = {d for d in decision_of.values() if d}
    ours = defaultdict(dict)                                   # decision -> {our opinion: 5-word sequences}
    for r in con.execute("SELECT opinion_id, decision_id, text FROM opinions WHERE decision_id = ANY(%s)",
                         (list(decisions),)):
        ours[r["decision_id"]][r["opinion_id"]] = shingles(r["text"])
    before_shelby = con.execute("SELECT count(*) AS n FROM citation_map WHERE citing_opinion_id = %s",
                                (SHELBY,)).fetchone()["n"]

copy_text = {}                                                 # the skipped copies' texts, read once from step 1.5
wanted = {c for c, d in decision_of.items() if d}
for op in map(json.loads, open(config.WORK / "opinions.jsonl")):
    if op["opinion_id"] in wanted:
        copy_text[op["opinion_id"]] = pick_text(op)[0]

counts, targets = Counter(), {}
for c in copies:
    d = decision_of[c]
    if not d:
        counts["copy of a decision we do not have"] += 1
    elif not copy_text.get(c):
        counts["copy without text"] += 1
    else:
        targets[c] = copy_targets(shingles(copy_text[c]), ours[d])
        counts["given to 1 opinion" if len(targets[c]) == 1 else
               "given to several opinions (combined copy)" if targets[c] else "no match: given to nobody"] += 1

with db.connect() as con:                                     # the exact rows to add, worked out once
    have = {(r["citing_opinion_id"], r["cited_opinion_id"]) for r in con.execute(
        "SELECT citing_opinion_id, cited_opinion_id FROM citation_map WHERE citing_opinion_id = ANY(%s)",
        (sorted({t for ts in targets.values() for t in ts}),))}
    rows = defaultdict(list)
    for r in con.execute("SELECT * FROM citation_map WHERE citing_opinion_id = ANY(%s)", (list(targets),)):
        rows[r["citing_opinion_id"]].append(r)
    new = rows_to_add(targets, rows, have)
    if apply:
        with con.cursor() as cur:
            cur.executemany("INSERT INTO citation_map (citing_opinion_id, cited_opinion_id, cited_cluster_id, depth) "
                            "VALUES (%s, %s, %s, %s)", new)
    gaining = {t for t, _, _, _ in new}
    still_empty = con.execute("""SELECT count(*) AS n FROM opinions o WHERE NOT EXISTS
                                 (SELECT 1 FROM citation_map m WHERE m.citing_opinion_id = o.opinion_id)
                                 AND NOT o.opinion_id = ANY(%s)""", (sorted(gaining),)).fetchone()["n"]
added = len(new)

shelby_copies = [c for c, ts in targets.items() if SHELBY in ts]
report = {"apply": apply, "skipped_copies_in_map": len(copies), **counts, "rows_added": added,
          "shelby_9515886_rows_before": before_shelby, "shelby_copies": shelby_copies,
          "our_opinions_still_without_rows": still_empty}
if apply:
    db.save_report("citation_remap", report)
else:
    print(json.dumps(report, indent=1))
    print("Dry run: nothing written. Run again with --apply to add the rows.")
