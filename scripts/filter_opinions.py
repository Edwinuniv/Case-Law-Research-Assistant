"""WEEK 1 - Read the 44.8 GB opinions file ONCE and keep only the opinions of our clusters (SR9).
It also writes (opinion id, cluster id) for EVERY opinion: we need it for the citation map.

Two ways to run it:
  A) streaming (nothing big is stored on disk):
     curl -sS https://storage.courtlistener.com/bulk-data/opinions-2024-12-31.csv.bz2 \
        | lbzip2 -dc | python -m scripts.filter_opinions -
  B) from a downloaded file (can be resumed with curl -C -), then delete it:
     python -m scripts.filter_opinions data/bulk/opinions-2024-12-31.csv.bz2 --delete
Outputs: data/work/opinions.jsonl, data/work/opinion_cluster_pairs.csv"""
import json
import sys
from pathlib import Path
from app import config
from app.bulk import read_rows, progress, save_filter_report

TEXT_FIELDS = ["html_with_citations", "html", "xml_harvard", "html_lawbox", "html_columbia",
               "html_anon_2020", "plain_text"]

source = sys.argv[1]
clusters = {json.loads(l)["cluster_id"] for l in open(config.WORK / "clusters.jsonl")}
n = kept = bad = 0
with read_rows(source) as rows, \
        open(config.WORK / "opinions.jsonl", "w") as out, \
        open(config.WORK / "opinion_cluster_pairs.csv", "w") as pairs:
    for n, row in enumerate(rows, 1):
        progress(n, every=200_000, label="opinions")
        try:
            oid, cid = int(row["id"]), int(row["cluster_id"])
        except (TypeError, ValueError):
            bad += 1                       # a row that could not be read: counted, never hidden
            continue
        pairs.write(f"{oid},{cid}\n")
        if cid in clusters:
            # keep only the best text field (the first non-empty one in TEXT_FIELDS order)
            field = next((f for f in TEXT_FIELDS if len((row.get(f) or "").strip()) > 200), None)
            out.write(json.dumps({"opinion_id": oid, "cluster_id": cid, "type": row.get("type"),
                                  "author_str": row.get("author_str") or "",
                                  "per_curiam": row.get("per_curiam") in ("t", "True", "true", "1"),
                                  **({field: row[field]} if field else {})}) + "\n")
            kept += 1
print(f"Done: {n:,} opinions read, {kept:,} kept for our {len(clusters):,} clusters, "
      f"{bad:,} unreadable rows skipped.")
save_filter_report("opinions", rows_read=n, kept=kept, unreadable_rows=bad)
if "--delete" in sys.argv and source != "-":
    Path(source).unlink()
    print(f"Deleted {source} (NFR12: we do not keep the full file).")
