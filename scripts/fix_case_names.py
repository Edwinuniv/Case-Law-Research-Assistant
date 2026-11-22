"""Repair case names already loaded: a trailing "Revisions: <date>" goes (SPEC 11, 2026-11-21; app/ingest.clean_case_name).
Changes decisions.case_name only. Restart the site afterwards (the citation index keeps the names in memory).
Usage: python -m scripts.fix_case_names            (dry run: lists each change)
       python -m scripts.fix_case_names --apply    (writes, and saves the report)"""
import sys
from app import db
from app.ingest import clean_case_name

apply = "--apply" in sys.argv
with db.connect() as con:
    rows = con.execute("SELECT decision_id, case_name FROM decisions ORDER BY decision_id").fetchall()
    changes = [(r["decision_id"], r["case_name"], clean_case_name(r["case_name"])) for r in rows
               if clean_case_name(r["case_name"]) != r["case_name"]]
    for did, old, new in changes:
        print(f"{did}: {old!r} -> {new!r}")
        if apply:
            con.execute("UPDATE decisions SET case_name = %s WHERE decision_id = %s", (new, did))
print(f"{len(changes)} of {len(rows)} names {'changed' if apply else 'would change (dry run; --apply to write)'}.")
if apply:
    db.save_report("case_names", {"changed": [{"decision_id": d, "old": o, "new": n} for d, o, n in changes]})
