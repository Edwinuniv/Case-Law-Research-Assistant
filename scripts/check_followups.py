"""Check eval/followups.jsonl (followups-v1) before committing it: the follow-up test set of EVALUATION.md
("Follow-up questions rule"). One pair per line: a first question, then a follow-up about its answer.
For every pair: valid JSON, an F id used once, a known tag, kind and split, an author (the set is written by the
team), both questions 3 to 1,000 characters (SR3) and different, the fields its tag needs, and for an answerable
follow-up the gold quote word for word in one of its gold decisions (like scripts/check_questions.py).
Usage: python -m scripts.check_followups [eval/followups.jsonl]"""
import json
import sys

KINDS = ("explain", "separate_opinion", "missing_detail", "false_premise", "invent_case", "injection")
REQUIRED = {"answerable": ["expected_answer", "gold_decision_ids", "gold_quote"],
            "unanswerable": ["why"], "adversarial": ["must_not_appear", "why"]}


def pair_problems(p, opinion_texts):
    """The problems of one pair; opinion_texts(decision_ids) -> the texts of those decisions' opinions."""
    out = []
    if not str(p.get("id", "")).startswith("F"):
        out.append("id must start with F (F001, ...), apart from eval-v1's A/U/X ids")
    if p.get("tag") not in REQUIRED:
        out.append(f"unknown tag {p.get('tag')!r}")
    if p.get("kind") not in KINDS:
        out.append(f"unknown kind {p.get('kind')!r} (one of {', '.join(KINDS)})")
    if p.get("split") not in ("tune", "test"):
        out.append("split must be tune or test")
    if not str(p.get("author", "")).strip():
        out.append("missing author (the set is written by the team)")
    for field in ("first_question", "follow_up"):
        if not 3 <= len(str(p.get(field, "")).strip()) <= 1000:
            out.append(f"{field} must have 3 to 1,000 characters (SR3)")
    if str(p.get("first_question", "")).strip().lower() == str(p.get("follow_up", "")).strip().lower():
        out.append("the follow-up is the same as the first question")
    # must_not_appear may be an empty list (an injection with no fake text); it must be present
    out += [f"missing {f}" for f in REQUIRED.get(p.get("tag"), [])
            if ((f not in p) if f == "must_not_appear" else not p.get(f))]
    if p.get("tag") == "answerable" and p.get("gold_decision_ids") and p.get("gold_quote"):
        from scripts.tune_search import norm          # the same matching as check_questions
        texts = opinion_texts(p["gold_decision_ids"])
        if not texts:
            out.append("gold decision NOT FOUND")
        elif not any(norm(p["gold_quote"]) in norm(t) for t in texts):
            out.append("gold_quote NOT FOUND word for word")
    return out


def check_lines(lines, opinion_texts):
    report = {"problems": {}, "counts": {}, "authors": {}, "pairs": 0}
    seen = set()
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            p = json.loads(line)
        except ValueError as e:
            report["problems"][f"line {n}"] = [f"not valid JSON ({e})"]
            continue
        report["pairs"] += 1
        found = pair_problems(p, opinion_texts)
        if p.get("id") in seen:
            found = ["duplicate id"] + found
        seen.add(p.get("id"))
        if found:
            report["problems"][f"{p.get('id')} (line {n})"] = found
        key = (p.get("tag"), p.get("split"))
        report["counts"][key] = report["counts"].get(key, 0) + 1
        author = str(p.get("author", "")).strip() or "?"
        report["authors"][author] = report["authors"].get(author, 0) + 1
    return report


def database_texts(ids):
    from app import db
    from scripts.tune_search import canonical               # a merged copy counts as the kept decision
    with db.connect() as con:
        return [r["text"] for r in con.execute("SELECT text FROM opinions WHERE decision_id = ANY(%s)",
                                               (list(canonical(ids)),))]


def main(argv):
    path = argv[0] if argv else "eval/followups.jsonl"
    report = check_lines(open(path, encoding="utf-8").read().splitlines(), database_texts)
    for where, found in report["problems"].items():
        print(f"{where}: {'; '.join(found)}")
    print(f"\n{report['pairs']} pair(s); counts (tag, split): {dict(sorted(report['counts'].items(), key=str))}")
    print(f"by author: {report['authors']}")
    print("no problems" if not report["problems"] else f"{len(report['problems'])} line(s) with problems")
    return 1 if report["problems"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
