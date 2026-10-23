"""WEEK 1 - Keep the part of the citation map where the CITING opinion is one of ours,
and find the cluster of each CITED opinion.  Output: data/work/citation_map.csv
Usage: python -m scripts.filter_citation_map"""
import json
import numpy as np
from app import config
from app.bulk import read_rows, progress, save_filter_report

ours = {json.loads(l)["opinion_id"] for l in open(config.WORK / "opinions.jsonl")}
pairs = np.loadtxt(config.WORK / "opinion_cluster_pairs.csv", delimiter=",", dtype=np.int64, ndmin=2)
pairs = pairs[np.argsort(pairs[:, 0])]               # sorted by opinion id -> fast lookup
opinion_ids, cluster_ids = pairs[:, 0], pairs[:, 1]

def cluster_of(opinion_id):
    i = np.searchsorted(opinion_ids, opinion_id)
    return int(cluster_ids[i]) if i < len(opinion_ids) and opinion_ids[i] == opinion_id else ""

n = kept = 0
with read_rows(config.BULK / config.BULK_FILES["citation-map"]) as rows, \
        open(config.WORK / "citation_map.csv", "w") as out:
    for n, row in enumerate(rows, 1):
        progress(n, every=1_000_000, label="citation-map rows")
        citing = int(row["citing_opinion_id"])
        if citing in ours:
            cited = int(row["cited_opinion_id"])
            out.write(f"{citing},{cited},{cluster_of(cited)},{row.get('depth') or 1}\n")
            kept += 1
print(f"Done: {n:,} rows read, {kept:,} kept (citations made by our {len(ours):,} opinions).")
save_filter_report("citation-map", rows_read=n, kept=kept)
