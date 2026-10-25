"""Find a decision's ID by name (for writing test questions).
Usage: python -m scripts.find_case "loper bright" """
import sys
from app import db

words = " ".join(sys.argv[1:])
with db.connect() as con:
    for d in con.execute("SELECT decision_id, case_name, date_filed, citations FROM decisions "
                         "WHERE case_name ILIKE %s ORDER BY date_filed", (f"%{words}%",)):
        print(d["decision_id"], "|", d["case_name"], "|", d["date_filed"], "|", ", ".join(d["citations"]))
