"""Check the corpus with the citation rules of app/scope.py (read-only).
Usage: python -m scripts.check_scope
Prints every decision that may not be a Supreme Court decision of 2000-2024 and is not yet in
app/scope.py. Check each by hand, then add it to OUT_OF_SCOPE (with what it really is) or REVIEWED_IN_SCOPE."""
from app import db, scope

with db.connect() as con:
    rows = con.execute("SELECT decision_id, case_name, date_filed, citations FROM decisions ORDER BY date_filed").fetchall()
known = [d for d in rows if d["decision_id"] in scope.OUT_OF_SCOPE]
new = [(d, p) for d in rows if d["decision_id"] not in scope.OUT_OF_SCOPE
       for p in [scope.problems(d["decision_id"], d["citations"])] if p]
print(f"{len(rows):,} decisions; {len(known)} still in the database although listed as out of scope"
      f" (run: python -m scripts.remove_out_of_scope)")
print(f"{len(new)} new decision(s) to check by hand:")
for d, p in new:
    print(f"  {d['decision_id']} {d['date_filed']} | {d['case_name'][:60]} | {'; '.join(p)}")
