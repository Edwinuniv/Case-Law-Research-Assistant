"""Remove the decisions listed in app/scope.py OUT_OF_SCOPE (their opinions and chunks go with them).
Usage: python -m scripts.remove_out_of_scope            (dry run: what would be removed)
       python -m scripts.remove_out_of_scope --apply    (removes them and writes an ingestion report)
No new embeddings are needed (the other chunks do not change); the BM25 cache rebuilds by itself."""
import sys
from app import db, scope

apply = "--apply" in sys.argv
with db.connect() as con:
    found = con.execute("""SELECT d.decision_id, d.case_name, d.date_filed,
                                  (SELECT count(*) FROM opinions o WHERE o.decision_id = d.decision_id) AS opinions,
                                  (SELECT count(*) FROM chunks c WHERE c.decision_id = d.decision_id) AS chunks
                           FROM decisions d WHERE d.decision_id = ANY(%s) ORDER BY d.date_filed""",
                        (list(scope.OUT_OF_SCOPE),)).fetchall()
for d in found:
    print(f"  {d['decision_id']} {d['date_filed']} | {d['case_name'][:50]} | {d['opinions']} opinion(s), "
          f"{d['chunks']} chunks | {scope.OUT_OF_SCOPE[d['decision_id']]}")
chunks = sum(d["chunks"] for d in found)
print(f"{len(found)} of {len(scope.OUT_OF_SCOPE)} listed decisions are in the database ({chunks} chunks).")
if not apply or not found:
    sys.exit("Dry run: nothing removed." if found else "Nothing to remove.")
with db.connect() as con:
    con.execute("DELETE FROM chunks WHERE decision_id = ANY(%s)", ([d["decision_id"] for d in found],))
    con.execute("DELETE FROM decisions WHERE decision_id = ANY(%s)", ([d["decision_id"] for d in found],))
    meta = db.get_settings().get("index_meta") or {}
    if meta:                        # keep the index statistics true (SPEC section 4 reads them)
        meta["chunks"] = con.execute("SELECT count(*) FROM chunks").fetchone()["count"]
        db.set_setting("index_meta", meta)
db.save_report("out_of_scope", {"removed": {d["decision_id"]: scope.OUT_OF_SCOPE[d["decision_id"]] for d in found},
                                "chunks": chunks})
print(f"Removed {len(found)} decisions and {chunks} chunks. Restart the website so the search reloads.")
