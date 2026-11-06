"""WEEK 3 - Step 3.5: compare chunk sizes 250 / 350 / 400 words on the TUNE split
(rule in EVALUATION.md, written first). For each size: rebuild the index (embeddings come from
data/work/embedding_cache, see export_for_colab --sizes), then measure the baseline search.
At the end the index is rebuilt with the size chosen by the rule, and chunk_max_words is saved.
Usage: python -m scripts.tune_chunks [250 350 400]   -> eval/runs/tune_chunks_<date>.json"""
import datetime
import json
import sys
from app import config, db, indexing
from app.search import Searcher
from scripts.tune_search import measure


def main():
    sizes = [int(a) for a in sys.argv[1:]] or [250, 350, 400]
    base = db.get_settings()
    questions = [json.loads(line) for line in open(config.EVAL_DIR / "questions.jsonl") if line.strip()]
    tune = [q for q in questions if q["tag"] == "answerable" and q["split"] == "tune"]
    print(f"{len(tune)} answerable TUNE questions (the test split is not used)")
    for size in sizes:                     # every embedding must already be computed (Colab), see above
        _, rows_ = indexing.make_rows(size)
        missing = [k for k, _ in indexing.plan_blocks([r["embed_text"] for r in rows_])
                   if not (indexing.CACHE / f"{k}.npy").exists()]
        if missing:
            sys.exit(f"{size} words: {len(missing)} blocks are not in the embedding cache. First run\n"
                     f"  python -m scripts.export_for_colab --sizes {' '.join(map(str, sizes))}\n"
                     "then compute them in Colab and unzip them into data/work/embedding_cache.")
    rows = []
    for size in sizes:
        print(f"\n--- {size} words: rebuilding the index ---", flush=True)
        meta = indexing.build_index(size, log=lambda m: print(m, flush=True) if "opinions ->" in m else None)
        searcher = Searcher()
        lists = {}
        for q in tune:
            _, dense, keyword = searcher.candidates(q["question"], int(base["fusion_pool"]))
            lists[q["id"]] = (dense, keyword)
        r = {"max_words": size, "chunks": meta["chunks"],
             **measure(searcher, tune, lists, base, int(base["top_k"]))}
        print(r, flush=True)
        rows.append(r)
    best = sorted(rows, key=lambda r: (-r["quote@8"], -r["mrr@10"], r["max_words"] != 350))[0]
    print(f"\n{'words':>6} {'chunks':>8} {'quote@8':>8} {'recall@5':>9} {'mrr@10':>7}")
    for r in rows:
        print(f"{r['max_words']:>6} {r['chunks']:>8,} {r['quote@8']:>8} {r['recall@5']:>9} {r['mrr@10']:>7}"
              f"{'  <- chosen by the rule' if r is best else ''}")
    if best["max_words"] != sizes[-1]:
        print(f"\nRebuilding the index with the chosen size ({best['max_words']} words)...", flush=True)
        indexing.build_index(best["max_words"], log=lambda m: None)
    db.set_setting("chunk_max_words", best["max_words"])
    date = datetime.datetime.now().isoformat(timespec="seconds")
    (config.EVAL_DIR / "runs").mkdir(exist_ok=True)
    out = config.EVAL_DIR / "runs" / f"tune_chunks_{date.replace(':', '-')}.json"
    json.dump({"date": date, "questions": [q["id"] for q in tune], "rows": rows, "chosen": best},
              open(out, "w"), indent=1)
    print(f"saved {out}")


if __name__ == "__main__":
    main()
