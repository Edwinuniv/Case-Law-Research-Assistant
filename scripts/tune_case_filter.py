"""METADATA (2026-11-06) - Measure the case-name filter on the TUNE split, search only (no model call).
The rule is in EVALUATION.md ("Case-name filter selection rule"), written before measuring.
For every TUNE question: the normal search (filter off), then, if the question names a case of our
corpus, the search limited to that decision (filter on). Saved in eval/runs/case_filter_<date>.json.
Usage: python -m scripts.tune_case_filter "note"
Needs Searcher.search(question, k, settings, decision_ids) (Yasser's search.py)."""
import sys
import json
import time
import inspect
import datetime
from app import config, db
from app.citations import CitationIndex, find_case_names
from app.pipeline import named_decisions
from app.search import Searcher
from scripts.tune_search import canonical, norm

note = " ".join(sys.argv[1:])
s = db.get_settings()
searcher = Searcher()
if "decision_ids" not in inspect.signature(searcher.search).parameters:
    sys.exit("Searcher.search has no decision_ids parameter yet (Yasser's search.py): nothing measured.")
index = CitationIndex()
questions = [json.loads(l) for l in open(config.EVAL_DIR / "questions.jsonl") if l.strip()]
tune = [q for q in questions if q["split"] == "tune"]


def run(q, decision_ids):
    """Search once; returns the rank of the gold decision, whether the gold quote is in the 8 passages,
    and the search time in ms."""
    t = time.perf_counter()
    if decision_ids:
        found = searcher.search(q["question"], k=int(s["retrieve_k"]), settings=s, decision_ids=decision_ids)
    else:
        found = searcher.search(q["question"], k=int(s["retrieve_k"]), settings=s)
    chosen = searcher.choose(q["question"], found, int(s["top_k"]), False)
    ms = (time.perf_counter() - t) * 1000
    chosen_ids = {p["chunk_id"] for p in chosen}
    order = [p["decision_id"] for p in chosen] + [p["decision_id"] for p in found if p["chunk_id"] not in chosen_ids]
    gold = canonical(q.get("gold_decision_ids") or [])
    rank = next((i + 1 for i, d in enumerate(order) if d in gold), None)
    quote = bool(q.get("gold_quote")) and any(norm(q["gold_quote"]) in norm(p["text"]) for p in chosen)
    return rank, quote, ms


per_question, switched_on_wrongly = {}, []
for q in tune:
    ids = named_decisions(q["question"], index)
    row = {"tag": q["tag"], "filter_decisions": ids}
    if q["tag"] == "answerable":
        row["off"] = dict(zip(("rank", "quote", "ms"), run(q, [])))
        row["on"] = dict(zip(("rank", "quote", "ms"), run(q, ids))) if ids else row["off"]
    elif ids:                                                   # adversarial or unanswerable
        # rule (3): a case name that must not appear (invented or mixed) must not switch the filter on
        forbidden = [f.lower() for f in q.get("must_not_appear") or [] if f]
        if any(index.decisions_named(name) and any(f in name.lower() for f in forbidden)
               for name in find_case_names(q["question"])):
            switched_on_wrongly.append(q["id"])
    per_question[q["id"]] = row
    print(f"{q['id']} ({q['tag']}): filter {'on ' + str(ids) if ids else 'off'}"
          + (f" | quote {row['off']['quote']} -> {row['on']['quote']}, rank {row['off']['rank']} -> {row['on']['rank']}"
             if q["tag"] == "answerable" else ""))

answerable = [r for r in per_question.values() if r["tag"] == "answerable"]
n = len(answerable) or 1


def summary(side):
    ranks = [r[side]["rank"] for r in answerable]
    return {"quote@8": round(sum(r[side]["quote"] for r in answerable) / n, 3),
            "recall@5": round(sum(1 for x in ranks if x and x <= 5) / n, 3),
            "mrr@10": round(sum(1 / x for x in ranks if x and x <= 10) / n, 3),
            "mean_search_ms": round(sum(r[side]["ms"] for r in answerable) / n, 1)}


result = {"date": datetime.datetime.now().isoformat(timespec="seconds"), "note": note, "split": "tune",
          "answerable": len(answerable),
          "answerable_with_filter": sum(1 for r in answerable if r["filter_decisions"]),
          "off": summary("off"), "on": summary("on"),
          "quotes_lost": [i for i, r in per_question.items() if r["tag"] == "answerable"
                          and r["off"]["quote"] and not r["on"]["quote"]],
          "other_questions_with_filter": [i for i, r in per_question.items()
                                          if r["tag"] != "answerable" and r["filter_decisions"]],
          "switched_on_for_an_invented_or_mixed_name": switched_on_wrongly,
          "search_settings": {k: s[k] for k in ("w_bm25", "w_separate", "fusion_pool", "retrieve_k", "top_k")}}
print(json.dumps(result, indent=1))
(config.EVAL_DIR / "runs").mkdir(exist_ok=True)
out = config.EVAL_DIR / "runs" / f"case_filter_{result['date'].replace(':', '-')}.json"
json.dump({**result, "per_question": per_question}, open(out, "w"), indent=1)
print(f"saved {out}")
