"""WEEK 3 - Choose the search settings on the TUNE split (rule in EVALUATION.md, written first).
Search only, no language model. For every combination of w_bm25 / w_separate / fusion_pool it
measures, on the answerable TUNE questions:
  quote@8  share of questions whose gold_quote is inside one of the 8 passages given to the model
  recall@5 / MRR@10  of the gold decision (as in eval_retrieval)
Usage: python -m scripts.tune_search            -> table + eval/runs/tune_search_<date>.json"""
import datetime
import itertools
import json
from app import config, db
from app.search import Searcher

GRID = {"w_bm25": [1.0, 1.5, 2.0, 3.0], "w_separate": [1.0, 0.5, 0.25], "fusion_pool": [50, 100]}


def norm(text):
    """Compare quotes without caring about curly quotes, spaces or line breaks."""
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'), ("­", ""), ("—", "-"), ("–", "-")):
        text = text.replace(a, b)
    return " ".join(text.lower().split())


def canonical(ids):
    """Gold decision ids as they are now: a copy merged into another decision counts as that one."""
    ids = [int(i) for i in ids]
    with db.connect() as con:
        rows = con.execute("SELECT cluster_id, decision_id FROM cluster_alias WHERE cluster_id = ANY(%s)",
                           (ids,)).fetchall()
    alias = {r["cluster_id"]: r["decision_id"] for r in rows}
    return {alias.get(i, i) for i in ids}


def measure(searcher, questions, lists, settings, top_k):
    quote_hits, ranks = 0, []
    for q in questions:
        dense, keyword = lists[q["id"]]
        best = searcher.fuse(dense, keyword, int(settings["retrieve_k"]), settings)
        chosen = best[:top_k]
        gold_quote = norm(q.get("gold_quote", ""))
        quote_hits += bool(gold_quote) and any(gold_quote in norm(searcher.by_id[c]["text"]) for c in chosen)
        order = [searcher.by_id[c]["decision_id"] for c in best]
        gold = q.setdefault("_gold", canonical(q["gold_decision_ids"]))
        ranks.append(next((i + 1 for i, d in enumerate(order) if d in gold), None))
    n = len(questions) or 1
    return {"quote@8": round(quote_hits / n, 3),
            "recall@5": round(sum(1 for r in ranks if r and r <= 5) / n, 3),
            "mrr@10": round(sum(1 / r for r in ranks if r and r <= 10) / n, 3)}


def main():
    base = db.get_settings()
    questions = [json.loads(line) for line in open(config.EVAL_DIR / "questions.jsonl") if line.strip()]
    tune = [q for q in questions if q["tag"] == "answerable" and q["split"] == "tune"]
    print(f"{len(tune)} answerable TUNE questions (the test split is not used)")
    searcher = Searcher()
    pool = max(GRID["fusion_pool"])
    lists = {}
    for q in tune:                                   # the two ranked lists, computed once per question
        _, dense, keyword = searcher.candidates(q["question"], pool)
        lists[q["id"]] = (dense, keyword)
    rows = []
    for w_bm25, w_sep, fpool in itertools.product(*GRID.values()):
        settings = {**base, "w_bm25": w_bm25, "w_separate": w_sep, "fusion_pool": fpool}
        rows.append({"w_bm25": w_bm25, "w_separate": w_sep, "fusion_pool": fpool,
                     **measure(searcher, tune, lists, settings, int(base["top_k"]))})
    baseline = next(r for r in rows if (r["w_bm25"], r["w_separate"], r["fusion_pool"]) == (1.0, 1.0, 50))
    # the rule: best quote@8, then best MRR@10, then closest to the baseline
    distance = lambda r: abs(r["w_bm25"] - 1) + abs(r["w_separate"] - 1) + (r["fusion_pool"] != 50)
    best = sorted(rows, key=lambda r: (-r["quote@8"], -r["mrr@10"], distance(r)))[0]
    print(f"{'w_bm25':>7} {'w_separate':>10} {'pool':>5} {'quote@8':>8} {'recall@5':>9} {'mrr@10':>7}")
    for r in rows:
        mark = "  <- baseline" if r is baseline else ("  <- chosen by the rule" if r is best else "")
        print(f"{r['w_bm25']:>7} {r['w_separate']:>10} {r['fusion_pool']:>5} {r['quote@8']:>8} "
              f"{r['recall@5']:>9} {r['mrr@10']:>7}{mark}")
    date = datetime.datetime.now().isoformat(timespec="seconds")
    (config.EVAL_DIR / "runs").mkdir(exist_ok=True)
    out = config.EVAL_DIR / "runs" / f"tune_search_{date.replace(':', '-')}.json"
    json.dump({"date": date, "questions": [q["id"] for q in tune], "baseline": baseline,
               "chosen": best, "rows": rows}, open(out, "w"), indent=1)
    print(f"saved {out}")


if __name__ == "__main__":
    main()
