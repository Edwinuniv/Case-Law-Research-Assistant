"""WEEK 10 - Step 10.2: compare the embedding models on the TUNE split (rule in EVALUATION.md,
written first). Search only, no language model, and the live index is NOT changed:
both models' passage vectors come from data/work/embedding_cache (see export_for_colab --model),
the meaning search is done here in memory (the same exact cosine search as PostgreSQL does), and the
keyword list (BM25), the fusion and the 8 chosen passages are exactly those of app/search.py.
Usage: python -m scripts.tune_embeddings   -> table + verdict + eval/runs/tune_embeddings_<date>.json"""
import datetime
import json
import sys
import time
import numpy as np
from fastembed import TextEmbedding
from app import config, db, indexing
from app.search import Searcher
from scripts.tune_search import measure, norm

BASELINE, CANDIDATE = config.EMBED_MODEL, "BAAI/bge-base-en-v1.5"


def passage_matrix(model, rows):
    """All passage vectors of one model, in the order of rows (one row per chunk)."""
    texts = [r["embed_text"] for r in rows]
    blocks = indexing.plan_blocks(texts, model)
    missing = [k for k, _ in blocks if not (indexing.CACHE / f"{k}.npy").exists()]
    if missing:
        sys.exit(f"{model}: {len(missing)} of {len(blocks)} blocks are not in the embedding cache. First run\n"
                 f"  python -m scripts.export_for_colab --model {model}\n"
                 "then compute them in Colab and unzip them into data/work/embedding_cache.")
    matrix = np.zeros((len(texts), config.EMBED_DIMS[model]), dtype=np.float32)
    for key, idx in blocks:
        matrix[idx] = np.load(indexing.CACHE / f"{key}.npy")
    return matrix


def question_vectors(model, questions):
    """Each question embedded on this computer's CPU, timed (criterion 4 of the rule)."""
    m = TextEmbedding(model, cache_dir=str(config.DATA / "models"))
    list(m.query_embed("warm-up"))                    # the first call loads the model: not timed
    vecs, seconds = {}, []
    for q in questions:
        start = time.perf_counter()
        v = np.array(list(m.query_embed(q["question"]))[0], dtype=np.float32)
        seconds.append(time.perf_counter() - start)
        vecs[q["id"]] = v / np.linalg.norm(v)
    return vecs, sum(seconds) / len(seconds)


def main():
    settings = db.get_settings()
    pool, top_k = int(settings["fusion_pool"]), int(settings["top_k"])
    questions = [json.loads(line) for line in open(config.EVAL_DIR / "questions.jsonl") if line.strip()]
    tune = [q for q in questions if q["tag"] == "answerable" and q["split"] == "tune"]
    print(f"{len(tune)} answerable TUNE questions (the test split is not used)", flush=True)

    searcher = Searcher()
    _, rows = indexing.make_rows(int(settings.get("chunk_max_words", 350)))
    ids = [r["chunk_id"] for r in rows]
    if set(ids) != set(searcher.by_id):
        sys.exit("The chunks in the database are not the chunks of the cache: run python -m scripts.seed --index")
    keyword = {q["id"]: searcher.keyword(q["question"], pool) for q in tune}

    results = {}
    for model in (BASELINE, CANDIDATE):
        print(f"\n--- {model} ---", flush=True)
        matrix = passage_matrix(model, rows)
        qvecs, sec = question_vectors(model, tune)
        lists = {}
        for q in tune:
            scores = matrix @ qvecs[q["id"]]          # cosine similarity (all vectors have length 1)
            top = np.argsort(-scores)[:pool]
            lists[q["id"]] = ([(ids[i], float(scores[i])) for i in top], keyword[q["id"]])
        hits = sorted(q["id"] for q in tune
                      if norm(q.get("gold_quote", "")) and any(
                          norm(q["gold_quote"]) in norm(searcher.by_id[c]["text"])
                          for c in searcher.fuse(*lists[q["id"]], int(settings["retrieve_k"]), settings)[:top_k]))
        results[model] = {"model": model, "dim": matrix.shape[1], "seconds_per_question": round(sec, 3),
                          **measure(searcher, tune, lists, settings, top_k), "quote_hits": hits}
        print({k: v for k, v in results[model].items() if k != "quote_hits"}, flush=True)
        del matrix

    base, cand = results[BASELINE], results[CANDIDATE]
    gained = len(cand["quote_hits"]) - len(base["quote_hits"])
    checks = {"(1) quote@8 higher by at least 2 questions": gained >= 2,
              "(2) recall@5 not lower": cand["recall@5"] >= base["recall@5"],
              "(3) MRR@10 not lower by more than 0.02": cand["mrr@10"] >= base["mrr@10"] - 0.02,
              "(4) under 0.5 s per question on this CPU": cand["seconds_per_question"] < 0.5}
    chosen = CANDIDATE if all(checks.values()) else BASELINE

    print(f"\n{'model':<24} {'dim':>4} {'quote@8':>8} {'recall@5':>9} {'mrr@10':>7} {'s/question':>11}")
    for r in (base, cand):
        print(f"{r['model']:<24} {r['dim']:>4} {r['quote@8']:>8} {r['recall@5']:>9} {r['mrr@10']:>7} "
              f"{r['seconds_per_question']:>11}{'  <- chosen by the rule' if r['model'] == chosen else ''}")
    print(f"\nquote@8 questions gained: {sorted(set(cand['quote_hits']) - set(base['quote_hits']))}, "
          f"lost: {sorted(set(base['quote_hits']) - set(cand['quote_hits']))}")
    for name, ok in checks.items():
        print(f"  {'OK  ' if ok else 'FAIL'} {name}")
    print(f"Chosen by the rule: {chosen}" + ("" if chosen == BASELINE else
          "  (nothing is changed yet: switching the live index is a separate step)"))

    date = datetime.datetime.now().isoformat(timespec="seconds")
    (config.EVAL_DIR / "runs").mkdir(exist_ok=True)
    out = config.EVAL_DIR / "runs" / f"tune_embeddings_{date.replace(':', '-')}.json"
    json.dump({"date": date, "questions": [q["id"] for q in tune], "settings": settings,
               "rows": [base, cand], "checks": checks, "chosen": chosen}, open(out, "w"), indent=1)
    print(f"saved {out}")


if __name__ == "__main__":
    main()
