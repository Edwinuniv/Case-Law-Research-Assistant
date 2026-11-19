"""Before a re-index: which passages would change their section label with the current app/chunking.py?
Compares the chunks stored in the database (cut by the code of the last re-index) with what chunk_opinion gives
now. Read-only: it changes nothing. A passage is "dangerous" when the stored label says it is the Court's
opinion but the new one names a separate opinion (concurring, dissenting, respecting): before the re-index the
model and check 6 of the verifier would take it for the Court's view.
Usage: python -m scripts.check_sections            (summary + the decisions concerned)
       python -m scripts.check_sections --examples (also one sentence of each dangerous decision)"""
import sys
from collections import defaultdict

from app import db
from app.chunking import chunk_opinion
from app.verify import SEPARATE_OPINION

MAX_WORDS = int(db.get_settings().get("chunk_max_words", 350))

with db.connect() as con:
    opinions = con.execute("""SELECT o.opinion_id, o.label, o.text, d.decision_id, d.case_name, d.date_filed
                              FROM opinions o JOIN decisions d USING (decision_id) ORDER BY o.opinion_id""").fetchall()
    stored = defaultdict(list)
    for r in con.execute("SELECT opinion_id, start_char, end_char, section FROM chunks ORDER BY opinion_id, ord"):
        stored[r["opinion_id"]].append(r)


def section_at(chunks, pos):
    """The section of the chunk that contains character pos (chunks are sorted, they do not overlap)."""
    for c in chunks:
        if c["start"] <= pos < c["end"]:
            return c["section"]
    return None


changed_opinions, changed_chunks, dangerous = 0, 0, defaultdict(list)
for o in opinions:
    new = chunk_opinion(o["text"], MAX_WORDS)
    old = stored.get(o["opinion_id"], [])
    old_simple = [(c["start_char"], c["end_char"], c["section"]) for c in old]
    if old_simple == [(c["start"], c["end"], c["section"]) for c in new]:
        continue
    changed_opinions += 1
    for c in old:                                   # compare each stored passage with the new label at its start
        now = section_at(new, c["start_char"])
        if now is None or now == c["section"]:
            continue
        changed_chunks += 1
        was_court = not SEPARATE_OPINION.search(f"{o['label']} {c['section']}")
        is_separate = bool(SEPARATE_OPINION.search(f"{o['label']} {now}"))
        if was_court and is_separate:
            dangerous[(o["decision_id"], o["case_name"], o["date_filed"].year)].append(
                (c["section"], now, o["text"][c["start_char"]:c["start_char"] + 160]))

print(f"{len(opinions):,} opinions, {sum(len(v) for v in stored.values()):,} stored passages, chunk size {MAX_WORDS}")
print(f"opinions whose passages would change: {changed_opinions}")
print(f"stored passages whose label would change: {changed_chunks}")
n_danger = sum(len(v) for v in dangerous.values())
print(f"of which shown as the Court's opinion today but a separate opinion in fact: {n_danger} "
      f"in {len(dangerous)} decision(s)")
for (did, name, year), items in sorted(dangerous.items(), key=lambda kv: -len(kv[1])):
    print(f"  {len(items):4} passage(s)  decision {did}  {name[:60]} ({year})  {items[0][0]!r} -> {items[0][1]!r}")
    if "--examples" in sys.argv:
        print(f"         e.g. {' '.join(items[0][2].split())[:150]}")
