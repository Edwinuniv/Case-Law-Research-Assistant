"""STEP 3.1 helper - find exact sentences for a test question's gold_quote.
Prints the sentences of the Court's opinion (not concurrences, dissents or the Syllabus) that
contain WORDS, with the decision id for gold_decision_ids. Copy the sentence exactly.
Usage: python -m scripts.find_quote "Bruen" "historical tradition"
       python -m scripts.find_quote "Bruen" "historical tradition" --all   (also other opinions)"""
import re
import sys
from app import db
from app.chunking import chunk_opinion

args = [a for a in sys.argv[1:] if not a.startswith("--")]
if len(args) != 2:
    sys.exit(__doc__)
case, words = args
show_all = "--all" in sys.argv
with db.connect() as con:
    rows = con.execute("""SELECT d.decision_id, d.case_name, d.date_filed, o.label, o.text
                          FROM opinions o JOIN decisions d USING (decision_id)
                          WHERE d.case_name ILIKE %s ORDER BY d.date_filed""", (f"%{case}%",)).fetchall()
if not rows:
    sys.exit(f"No decision whose name contains '{case}'. Try python -m scripts.find_case \"{case}\"")
found = 0
for o in rows:
    for c in chunk_opinion(o["text"]):
        court = c["section"].startswith(("Opinion of the Court", "Per curiam")) or \
            o["label"].startswith(("Majority", "Unanimous", "Per curiam"))
        if c["is_syllabus"] or not (court or show_all):
            continue
        for s in re.split(r"(?<=[.?!])\s+", c["text"]):
            if words.lower() in s.lower() and 3 <= len(s.split()) <= 60:
                found += 1
                print(f"decision {o['decision_id']} | {o['case_name'][:50]} ({o['date_filed'].year}) | {c['section']}\n  {s}\n")
print(f"{found} sentence(s)." + ("" if found or show_all else " Nothing in the Court's opinion: try other words, or --all."))
