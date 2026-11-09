"""Join words broken at a line end ("mar- riage" -> "marriage") and remove page markers ("*490"),
see app/linebreaks.py.
Usage: python -m scripts.fix_line_breaks            (dry run: what would change, nothing written)
       python -m scripts.fix_line_breaks --apply    (writes the repaired texts and an ingestion report)
After --apply, rebuild the passages: python -m scripts.seed --index (changed blocks need new embeddings).
Do NOT apply before the team agrees: Edwin's quote-matching measurement needs the run 2 passages."""
import re
import sys
from collections import Counter
from app import db, linebreaks

apply = "--apply" in sys.argv
with db.connect() as con:
    opinions = con.execute("SELECT opinion_id, decision_id, text FROM opinions ORDER BY opinion_id").fetchall()
mapping = linebreaks.repairs(linebreaks.vocabulary(o["text"] for o in opinions))

changed, decisions, used, left = [], set(), Counter(), Counter()
words = markers = 0
examples, kept = [], []                    # page markers removed / star numbers kept (pinpoint citations)
STAR_NUMBER = re.compile(r" \*{1,2}\d{1,4}(?= )")
for o in opinions:
    fixed, w, m = linebreaks.fix_opinion(o["text"], mapping)
    for match in linebreaks.BROKEN.finditer(o["text"]):
        key = (match.group(1).lower(), match.group(2))
        (used if key in mapping else left)[key] += 1
    if w or m:
        changed.append((o["opinion_id"], fixed))
        decisions.add(o["decision_id"])
        words, markers = words + w, markers + m
    removed = {h.start() for h in linebreaks.PAGE_MARKER.finditer(o["text"])}
    for h in STAR_NUMBER.finditer(o["text"]):                # every 10th opinion, to spread the examples
        context = o["text"][max(0, h.start() - 50):h.end() + 50].replace("\n", " ")
        target = examples if h.start() in removed else kept
        if len(target) < 8 and o["opinion_id"] % 10 == 0:
            target.append(context)

print(f"{len(changed):,} opinions in {len(decisions):,} decisions to repair: "
      f"{words:,} broken words joined, {markers:,} page markers removed")
print("most frequent repairs (check each one):")
for (a, b), n in used.most_common(30):
    print(f"  {a}- {b} -> {mapping[(a, b)]}  ({n})")
print("most frequent pairs LEFT as they are (check none is a broken word we should repair):")
for (a, b), n in left.most_common(15):
    print(f"  {a}- {b}  ({n})")
print("page markers REMOVED, before (check each is a page number inside the text):")
for e in examples:
    print(f"  ...{e}...")
print("star numbers KEPT (check each is a citation to a LEXIS/Westlaw page):")
for e in kept:
    print(f"  ...{e}...")
if not apply:
    sys.exit("Dry run: nothing written. Check the lists above, then run again with --apply.")
with db.connect() as con:
    for opinion_id, fixed in changed:
        con.execute("UPDATE opinions SET text = %s WHERE opinion_id = %s", (fixed, opinion_id))
db.save_report("line_break_fix", {"opinions": len(changed), "decisions": len(decisions), "words": words,
                                  "page_markers": markers,
                                  "repairs": {f"{a}- {b}": mapping[(a, b)] for (a, b), _ in used.most_common()}})
print(f"{len(changed):,} opinions repaired. Now rebuild the passages: python -m scripts.seed --index")
