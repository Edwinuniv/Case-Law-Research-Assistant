"""WEEK 3 - Measure the reranker variants on the TUNE split (rule in EVALUATION.md, written first).
Search + reranker only, no language model.
  baseline  first 8 passages of the fused list
  A         reranker over the fused top 20
  B         reranker over the fused top 50
  C         reranker over all passages of the top 3 decisions (decision first, then passage)
Prints quote@8 and the mean reranking time, per question and in total.
Usage: python -m scripts.tune_rerank          -> eval/runs/tune_rerank_<date>.json"""
import datetime
import json
import time
from app import config, db
from app.search import Searcher
from scripts.tune_search import norm


def has_quote(passages, quote):
    return bool(quote) and any(quote in norm(p["text"]) for p in passages)


def main():
    settings = db.get_settings()
    top_k = int(settings["top_k"])
    questions = [json.loads(line) for line in open(config.EVAL_DIR / "questions.jsonl") if line.strip()]
    tune = [q for q in questions if q["tag"] == "answerable" and q["split"] == "tune"]
    print(f"{len(tune)} answerable TUNE questions (the test split is not used)")
    searcher = Searcher()
    searcher.choose("warm-up", [searcher.chunks[0]], 1, True)      # load the reranker before timing
    variants = {"baseline": None, "A_fused20": 20, "B_fused50": 50, "C_top3_decisions": "decisions"}
    hits = {v: 0 for v in variants}
    seconds = {v: 0.0 for v in variants}
    per_question = {}
    for q in tune:
        found = searcher.search(q["question"], k=50, settings=settings)
        quote, row = norm(q.get("gold_quote", "")), {}
        for name, pool in variants.items():
            t = time.perf_counter()
            if pool is None:
                chosen = found[:top_k]
            else:
                candidates = (searcher.passages_of_top_decisions(found, 3) if pool == "decisions"
                              else found[:pool])
                chosen = searcher.choose(q["question"], candidates, top_k, True)
            seconds[name] += time.perf_counter() - t
            ok = has_quote(chosen, quote)
            hits[name] += ok
            row[name] = ok
        per_question[q["id"]] = row
        print(f"{q['id']}: " + "  ".join(f"{n}={'yes' if row[n] else 'no '}" for n in variants), flush=True)
    n = len(tune) or 1
    result = {v: {"quote@8": round(hits[v] / n, 3), "mean_seconds": round(seconds[v] / n, 2)} for v in variants}
    print(f"\n{'variant':18} {'quote@8':>8} {'mean s':>7}")
    for v, r in result.items():
        print(f"{v:18} {r['quote@8']:>8} {r['mean_seconds']:>7}")
    better = [v for v in variants if v != "baseline" and result[v]["quote@8"] > result["baseline"]["quote@8"]
              and result[v]["mean_seconds"] <= 5]
    chosen = min(better, key=lambda v: (-result[v]["quote@8"], result[v]["mean_seconds"])) if better else "baseline"
    print(f"chosen by the rule: {chosen}")
    date = datetime.datetime.now().isoformat(timespec="seconds")
    (config.EVAL_DIR / "runs").mkdir(exist_ok=True)
    out = config.EVAL_DIR / "runs" / f"tune_rerank_{date.replace(':', '-')}.json"
    json.dump({"date": date, "questions": [q["id"] for q in tune], "result": result, "chosen": chosen,
               "per_question": per_question}, open(out, "w"), indent=1)
    print(f"saved {out}")


if __name__ == "__main__":
    main()
