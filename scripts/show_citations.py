"""WEEK 8, step 8.3 - Every citation of a saved run: the ones SHOWN with a problem (the separate checker,
SR38: the goal is zero), the ones the verifier REMOVED, and the quotes not found, traced to their decision
(to see the effect of the missing "fi"/"fl" letters). Reads the database only: no model call.
Usage: python -m scripts.show_citations RUN_ID          -> TUNE split + adversarial questions (as the metrics)
       python -m scripts.show_citations RUN_ID --test   -> TEST split, once, after tau_abstain is chosen"""
import re
import sys
from collections import Counter
from app import db, evaluate
from app.pipeline import ANSWERED, LOW_CONFIDENCE

CITATION_PROBLEM = re.compile(r"citation|case name|year of the decision")
# Words whose "fi"/"fl" letters were lost when CourtListener made the text ("frst", "affrm"; told Yasser)
MISSING_FI_FL = re.compile(r"suffcient|frst|defnition|signifcant|specifc|benefts|fnal|infuence|confict|refect|"
                           r"offcer|fnding|frearm|infict|affrm|fduciary", re.I)


def keep_split(pairs, split):
    """Same questions as evaluate.metrics(split): that split, plus every adversarial question."""
    return [(q, r) for q, r in pairs if q["split"] == split or q["tag"] == "adversarial"]


def collect(pairs, s):
    shown, removed, quote_not_found = [], [], Counter()
    for q, r in pairs:
        status = evaluate.status_at(r, s)
        if status in (ANSWERED, LOW_CONFIDENCE):                          # only what a visitor would see
            for sentence, problems in zip(r["sentences"], r["false_by_sentence"]):
                shown += [{"id": q["id"], "status": status, "text": sentence.get("text", ""), "problem": p}
                          for p in problems]
        for sentence in r["removed"]:
            for p in sentence["problems"]:
                if p.startswith("quote not found"):
                    for pid in sentence["sources"]:                       # P2 is the 2nd decision of the ranked list
                        i = int(pid[1:]) - 1
                        if 0 <= i < len(r["ranked_decisions"]):
                            quote_not_found[r["ranked_decisions"][i]] += 1
                elif CITATION_PROBLEM.search(p):
                    removed.append({"id": q["id"], "text": sentence["text"], "problem": p})
    return {"shown": shown, "removed": removed, "quote_not_found": dict(quote_not_found)}


def main(argv):
    run_id, split = int(argv[0]), "test" if "--test" in argv else "tune"
    s = db.get_settings()
    pairs = keep_split(evaluate.load_run(run_id), split)
    report = collect(pairs, s)
    print(f"Run {run_id} ({evaluate.run_status(run_id)}), {split} split + adversarial: {len(pairs)} questions, "
          f"tau_abstain {s['tau_abstain']}")

    print(f"\n== Citations SHOWN with a problem (goal: 0): {len(report['shown'])} ==")
    for x in report["shown"]:
        print(f"  {x['id']} [{x['status']}] {x['problem']}\n      \"{x['text'][:150]}\"")

    print(f"\n== Citations and case names REMOVED by the verifier: {len(report['removed'])} ==")
    for kind, n in Counter(x["problem"].split(":")[0] for x in report["removed"]).most_common():
        print(f"  {n:3}  {kind}")
    for x in report["removed"]:
        print(f"  {x['id']} {x['problem']}\n      \"{x['text'][:150]}\"")

    ids = list(report["quote_not_found"])
    with db.connect() as con:
        names = {r["decision_id"]: r["case_name"] for r in con.execute(
            "SELECT decision_id, case_name FROM decisions WHERE decision_id = ANY(%s)", (ids,))}
        broken = {r["decision_id"] for r in con.execute(
            "SELECT DISTINCT decision_id FROM chunks WHERE decision_id = ANY(%s) AND text ~* %s",
            (ids, MISSING_FI_FL.pattern))}
    total = sum(report["quote_not_found"].values())
    in_broken = sum(n for d, n in report["quote_not_found"].items() if d in broken)
    print(f"\n== Quotes not found (check 2), by decision: {total}, of which {in_broken} in decisions "
          f"with missing \"fi\"/\"fl\" letters ==")
    for d, n in sorted(report["quote_not_found"].items(), key=lambda x: -x[1]):
        print(f"  {n:3}  {names.get(d, d)}{'   <- missing fi/fl letters' if d in broken else ''}")


if __name__ == "__main__":
    main(sys.argv[1:])
