"""WEEK 1 - Prepare the citation table (SR12): every citation in CourtListener -> cluster id.
Output: data/work/citations.csv.gz   Usage: python -m scripts.filter_citations"""
import gzip
from app import config
from app.bulk import read_rows, progress, save_filter_report

n = 0
with read_rows(config.BULK / config.BULK_FILES["citations"]) as rows, \
        gzip.open(config.WORK / "citations.csv.gz", "wt") as out:
    for n, row in enumerate(rows, 1):
        progress(n, every=1_000_000, label="citations")
        vol, rep, page, cid = row["volume"], row["reporter"], row["page"], row["cluster_id"]
        if vol and rep and page and cid:
            out.write(f"{vol}\t{rep}\t{page}\t{cid}\n")
print(f"Done: {n:,} citations written.")
save_filter_report("citations", rows_read=n)
