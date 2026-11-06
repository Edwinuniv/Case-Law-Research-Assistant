"""Put back the "fi"/"fl" letters lost in PDF texts ("frst" -> "first"), see app/ligatures.py.
Usage: python -m scripts.fix_ligatures            (dry run: what would change, nothing written)
       python -m scripts.fix_ligatures --apply    (writes the repaired texts and an ingestion report)
After --apply, rebuild the passages: python -m scripts.seed --index (changed blocks need new embeddings)."""
import sys
from collections import Counter
from psycopg.types.json import Jsonb
from app import db, ligatures

apply = "--apply" in sys.argv
with db.connect() as con:
    opinions = con.execute("SELECT opinion_id, decision_id, text FROM opinions ORDER BY opinion_id").fetchall()
mapping = ligatures.repairs(ligatures.vocabulary(o["text"] for o in opinions))

changed, used, decisions = [], Counter(), set()
for o in opinions:
    fixed, hits = ligatures.fix_opinion(o["text"], mapping)
    if hits:
        changed.append((o["opinion_id"], fixed))
        decisions.add(o["decision_id"])
        used.update(w.lower() for w in ligatures.WORD.findall(o["text"]) if w.lower() in mapping)

print(f"{len(mapping):,} broken word forms known; {len(changed):,} opinions in {len(decisions):,} decisions "
      f"to repair ({sum(used.values()):,} words)")
print("most frequent repairs:")
for word, n in used.most_common(25):
    print(f"  {word} -> {mapping[word]}  ({n})")
if not apply:
    sys.exit("Dry run: nothing written. Check the list above, then run again with --apply.")
with db.connect() as con:
    for opinion_id, fixed in changed:
        con.execute("UPDATE opinions SET text = %s WHERE opinion_id = %s", (fixed, opinion_id))
    con.execute("INSERT INTO ingestion_reports (kind, report) VALUES ('ligature_fix', %s)",
                (Jsonb({"opinions": len(changed), "decisions": len(decisions), "words": sum(used.values()),
                        "repairs": {w: mapping[w] for w, _ in used.most_common()}}),))
print(f"{len(changed):,} opinions repaired. Now rebuild the passages: python -m scripts.seed --index")
