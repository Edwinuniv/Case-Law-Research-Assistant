"""WEEK 10 (before choosing an improvement) - WHY is the gold quote not among the 8 passages?
Search only, no language model. For every answerable question whose gold_quote is NOT inside the
8 passages given to the model, it prints where the passage holding the quote really is:
  fused rank    its rank in the full fused list (fusion_pool widened to 3000)
  meaning rank  its rank in the pgvector (embedding) list      - None = not in the first 3000
  keyword rank  its rank in the BM25 list                       - None = no keyword in common
  n/8 gold      how many of the 8 chosen passages come from the gold decision
TUNE split only by default (the TEST split is not looked at while choosing); --all for both.
Usage: python -m scripts.diagnose_quotes [--all]   -> table + eval/runs/diagnose_quotes_<date>.json"""
import sys
import json
import datetime
from app import config, db
from app.search import Searcher
from scripts.tune_search import canonical, norm

WIDE = 3000
use_all = "--all" in sys.argv
s = db.get_settings()
searcher = Searcher()
questions = [json.loads(l) for l in open(config.EVAL_DIR / "questions.jsonl") if l.strip()]
answerable = [q for q in questions if q["tag"] == "answerable" and (use_all or q.get("split", "tune") == "tune")]


def rank_of(ids, target):
    return next((i + 1 for i, c in enumerate(ids) if c in target), None)


rows = []
for q in answerable:
    gold, quote = canonical(q["gold_decision_ids"]), norm(q["gold_quote"])
    chosen = searcher.search(q["question"], k=int(s["retrieve_k"]), settings=s)[:int(s["top_k"])]
    row = {"id": q["id"], "split": q.get("split", "tune"),
           "chosen_from_gold": sum(p["decision_id"] in gold for p in chosen)}
    if any(quote in norm(p["text"]) for p in chosen):
        row["result"] = "hit"
    else:
        target = {c["chunk_id"] for c in searcher.chunks
                  if c["decision_id"] in gold and quote in norm(c["text"])}
        if not target:
            row["result"] = "quote not found word for word in one chunk"
        else:
            _, dense, keyword = searcher.candidates(q["question"], WIDE)
            fused = searcher.fuse(dense, keyword, WIDE, {**s, "fusion_pool": WIDE})
            row.update(result="miss", fused_rank=rank_of(fused, target),
                       meaning_rank=rank_of([c for c, _ in dense], target),
                       keyword_rank=rank_of([c for c, _ in keyword], target))
    rows.append(row)
    if row["result"] == "miss":
        print(f"{q['id']}: MISS - fused rank {row['fused_rank']}, meaning rank {row['meaning_rank']}, "
              f"keyword rank {row['keyword_rank']}, {row['chosen_from_gold']}/8 from the gold decision")
    else:
        print(f"{q['id']}: {row['result'].upper() if row['result'] == 'hit' else row['result']}")

misses = [r for r in rows if r["result"] == "miss"]
summary = {
    "date": datetime.datetime.now().isoformat(timespec="seconds"),
    "split": "all" if use_all else "tune",
    "questions": len(rows),
    "hits": sum(r["result"] == "hit" for r in rows),
    "misses": len(misses),
    "quote_not_found": sum(r["result"] not in ("hit", "miss") for r in rows),
    "misses_fused_rank_9_20": sum(1 for r in misses if r["fused_rank"] and r["fused_rank"] <= 20),
    "misses_with_8_of_8_from_gold": sum(r["chosen_from_gold"] == 8 for r in misses),
    "misses_keyword_ahead_of_meaning": sum(1 for r in misses if r["keyword_rank"] and
                                           (r["meaning_rank"] is None or r["keyword_rank"] < r["meaning_rank"])),
}
print(json.dumps(summary, indent=1))
(config.EVAL_DIR / "runs").mkdir(exist_ok=True)
out = config.EVAL_DIR / "runs" / f"diagnose_quotes_{summary['date'].replace(':', '-')}.json"
json.dump({**summary, "rows": rows}, open(out, "w"), indent=1)
print("saved", out)
