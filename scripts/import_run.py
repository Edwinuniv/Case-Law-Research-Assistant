"""DEFENCE - Load a run saved in eval/runs (scripts/export_run.py, scripts/reverify_run.py) into the database of
DATABASE_URL, as it was: its date, settings, status and results. The online database has no evaluation run (the
dump was made before run 2), so the admin pages Runs, Compare and Threshold preview were empty. A file is imported
once: the note keeps its name, and a second import is refused. The test questions must be seeded first.
Usage: python -m scripts.import_run eval/runs/eval_run2_reverified.json
       DATABASE_URL="postgresql://...public url..." python -m scripts.import_run eval/runs/<file>.json   (online)"""
import sys
import json
from pathlib import Path
from psycopg.types.json import Jsonb
from app import db


def import_run(path):
    path = Path(path)
    saved = json.load(open(path))
    marker = f"[imported from {path.name}]"
    with db.connect() as con:
        if con.execute("SELECT 1 FROM eval_runs WHERE note LIKE %s", (f"%{marker}%",)).fetchone():
            sys.exit(f"{path.name} already imported: nothing done.")
        run_id = con.execute("INSERT INTO eval_runs (created_at, trigger, status, settings, note) "
                             "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                             (saved["created_at"], saved["trigger"], saved["status"], Jsonb(saved["settings"]),
                              f"{saved['note']} {marker}")).fetchone()["id"]
        for r in saved["results"]:
            con.execute("INSERT INTO eval_results (run_id, question_id, tag, split, result) VALUES (%s,%s,%s,%s,%s)",
                        (run_id, r["question_id"], r["tag"], r["split"], Jsonb(r["result"])))
    return run_id


if __name__ == "__main__":
    for f in sys.argv[1:]:
        print(f"{f} -> run {import_run(f)}")
