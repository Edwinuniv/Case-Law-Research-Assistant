"""STEP 3.1 helper - check a questions file before committing it.
For every line: valid JSON, required fields, known tag and split, unique id; for answerable
questions, the gold decisions exist and the gold_quote appears word for word in one of their opinions.
Usage: python -m scripts.check_questions eval/questions_yasser.jsonl"""
import json
import sys
from app import db
from scripts.tune_search import canonical, norm

REQUIRED = {"answerable": ["question", "expected_answer", "gold_decision_ids", "gold_quote"],
            "unanswerable": ["question", "why"], "adversarial": ["question", "must_not_appear", "why"]}
path = sys.argv[1] if len(sys.argv) > 1 else "eval/questions.jsonl"
problems, ids, counts = 0, set(), {}
with db.connect() as con:
    for n, line in enumerate(open(path, encoding="utf-8"), 1):
        if not line.strip():
            continue
        try:
            q = json.loads(line)
        except ValueError as e:
            print(f"line {n}: NOT valid JSON ({e})"); problems += 1; continue
        qid, tag = q.get("id", f"line {n}"), q.get("tag")
        errors = []
        if qid in ids:
            errors.append("duplicate id")
        ids.add(qid)
        if tag not in REQUIRED:
            errors.append(f"unknown tag {tag!r}")
        if q.get("split") not in ("tune", "test"):
            errors.append("split must be tune or test")
        errors += [f"missing {f}" for f in REQUIRED.get(tag, []) if not q.get(f)]
        if tag == "answerable" and q.get("gold_decision_ids") and q.get("gold_quote"):
            gold = canonical(q["gold_decision_ids"])        # a merged copy counts as the kept decision
            texts = [r["text"] for r in con.execute("SELECT text FROM opinions WHERE decision_id = ANY(%s)",
                                                    (list(gold),))]
            if not texts:
                errors.append("gold decision NOT FOUND")
            elif not any(norm(q["gold_quote"]) in norm(t) for t in texts):
                errors.append("gold_quote NOT FOUND word for word")
        counts[(tag, q.get("split"))] = counts.get((tag, q.get("split")), 0) + 1
        problems += bool(errors)
        print(f"{qid}: " + ("; ".join(errors) if errors else "ok"))
print("\ncounts (tag, split):", dict(sorted(counts.items(), key=str)))
print("no problems" if not problems else f"{problems} line(s) with problems")
sys.exit(1 if problems else 0)
