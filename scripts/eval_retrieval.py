"""WEEK 3 - Measure ONLY the search (no language model needed), on the answerable questions.
Usage: python -m scripts.eval_retrieval "note"            (fused order, the baseline)
       python -m scripts.eval_retrieval "note" --rerank   (after the reranker, week 10)
       python -m scripts.eval_retrieval "note" --split test   (only the TEST or the TUNE questions;
                                                  the numbers for the report come from the TEST split)"""
import sys
import json
import datetime
from app import config, db
from app.search import Searcher
from scripts.tune_search import canonical, norm

use_rerank = "--rerank" in sys.argv
split = sys.argv[sys.argv.index("--split") + 1] if "--split" in sys.argv else "all"
if split not in ("all", "tune", "test"):
    sys.exit("--split must be tune or test")
note = " ".join(a for i, a in enumerate(sys.argv[1:], 1)
                if not a.startswith("--") and sys.argv[i - 1] != "--split")
s = db.get_settings()
searcher = Searcher()
questions = [json.loads(l) for l in open(config.EVAL_DIR / "questions.jsonl") if l.strip()]
answerable = [q for q in questions if q["tag"] == "answerable" and split in ("all", q.get("split", "tune"))]

ranks, quote_hits, quote_ids = {}, 0, []
for q in answerable:
    found = searcher.search(q["question"], k=int(s["retrieve_k"]), settings=s)
    chosen = searcher.choose(q["question"], found, int(s["top_k"]), use_rerank)
    chosen_ids = {p["chunk_id"] for p in chosen}
    order = [p["decision_id"] for p in chosen] + [p["decision_id"] for p in found if p["chunk_id"] not in chosen_ids]
    gold = canonical(q["gold_decision_ids"])
    hit = bool(q.get("gold_quote")) and any(norm(q["gold_quote"]) in norm(p["text"]) for p in chosen)
    quote_hits += hit
    if hit:
        quote_ids.append(q["id"])
    ranks[q["id"]] = next((i + 1 for i, d in enumerate(order) if d in gold), None)
    print(f"{q['id']}: {'rank ' + str(ranks[q['id']]) if ranks[q['id']] else 'NOT in top ' + str(len(order))}")

n = len(ranks) or 1
r = list(ranks.values())
result = {"date": datetime.datetime.now().isoformat(timespec="seconds"), "note": note,
          "reranker": use_rerank, "split": split, "questions": len(ranks),
          **{f"recall@{k}": round(sum(1 for x in r if x and x <= k) / n, 3) for k in (1, 5, 10, 20)},
          "mrr@10": round(sum(1 / x for x in r if x and x <= 10) / n, 3),
          "quote@8": round(quote_hits / n, 3),   # gold_quote inside the passages given to the model
          "search_settings": {k: s[k] for k in ("w_bm25", "w_separate", "fusion_pool")}}
print(json.dumps(result, indent=1))
(config.EVAL_DIR / "runs").mkdir(exist_ok=True)
out = config.EVAL_DIR / "runs" / f"retrieval_{result['date'].replace(':', '-')}.json"
json.dump({**result, "ranks": ranks, "quote_hits": quote_ids}, open(out, "w"), indent=1)
print(f"saved {out}")
