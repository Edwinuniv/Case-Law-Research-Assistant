"""WEEK 1 - Keep only the opinion clusters (decisions) of our dockets and date range.
Output: data/work/clusters.jsonl   Usage: python -m scripts.filter_clusters"""
import json
from app import config
from app.bulk import read_rows, progress, save_filter_report

dockets = json.load(open(config.WORK / "dockets.json"))
n = kept = 0
with read_rows(config.BULK / config.BULK_FILES["opinion-clusters"]) as rows, \
        open(config.WORK / "clusters.jsonl", "w") as out:
    for n, row in enumerate(rows, 1):
        progress(n)
        docket = dockets.get(row["docket_id"])
        date = (row.get("date_filed") or "")[:10]
        if docket is None or not (config.DATE_FROM <= date <= config.DATE_TO):
            continue
        name = row.get("case_name") or row.get("case_name_full") or row.get("case_name_short") \
            or docket["case_name"] or "(unnamed case)"
        out.write(json.dumps({
            "cluster_id": int(row["id"]), "docket_id": int(row["docket_id"]),
            "docket_number": docket["docket_number"], "case_name": name, "date_filed": date,
            "precedential_status": row.get("precedential_status"),
            "source_url": f"https://www.courtlistener.com/opinion/{row['id']}/{row.get('slug') or 'case'}/",
        }) + "\n")
        kept += 1
print(f"Done: {n:,} clusters read, {kept:,} kept ({config.COURT}, {config.DATE_FROM} to {config.DATE_TO}).")
save_filter_report("opinion-clusters", rows_read=n, kept=kept)
