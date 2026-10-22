"""WEEK 1 - Keep only the dockets of our court.  Output: data/work/dockets.json
Usage: python -m scripts.filter_dockets"""
import json
from app import config
from app.bulk import read_rows, progress, save_filter_report

config.WORK.mkdir(parents=True, exist_ok=True)
kept, n = {}, 0
with read_rows(config.BULK / config.BULK_FILES["dockets"]) as rows:
    for n, row in enumerate(rows, 1):
        progress(n)
        if row["court_id"] == config.COURT:
            kept[row["id"]] = {"docket_number": row.get("docket_number") or "",
                               "case_name": row.get("case_name") or ""}
json.dump(kept, open(config.WORK / "dockets.json", "w"))
print(f"Done: {n:,} dockets read, {len(kept):,} kept for court '{config.COURT}'.")
save_filter_report("dockets", rows_read=n, kept=len(kept))
