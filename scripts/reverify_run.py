"""WEEK 8, step 8.2 - Check a run's saved sentences again with the changed verifier (EVALUATION.md, quote matching
selection rule). Same drafts (the sentences the model wrote in the run), same passages (found again by the same
search, same settings); the model is asked nothing, except the judge for a sentence that is newly kept.
Every question is rechecked (the TEST split is needed later, with the verifier that is kept), but only the TUNE
split + adversarial questions are listed and measured here: TEST is reported once, with run_eval --test.
The run kept the quote of removed sentences only, so a kept sentence gets every check again except the quote
check: the change makes the quote and the passage alike in the same way, so it can only find more quotes.
Usage: python -m scripts.reverify_run eval/runs/eval_run2.json   -> eval/runs/eval_run2_reverified.json"""
import sys
import json
from app import config, evaluate
from app.pipeline import support_score
from app.verify import check_sentence, count_fabrications, groundedness, norm

QUOTE_NOT_FOUND = "quote not found"


def ranked(chosen, found):
    ids = [p["decision_id"] for p in chosen]
    return ids + [p["decision_id"] for p in found if p["decision_id"] not in ids]


def recheck(q, r, s, chosen, index, judge, shown):
    passages = {f"P{i + 1}": p for i, p in enumerate(chosen)}
    kept, removed, judgements, newly = [], [], [], []
    for sentence, judgement in zip(r["sentences"], r["judgements"]):         # kept in the run: all checks but 2
        problems = [p for p in check_sentence({**sentence, "quote": ""}, passages, index)
                    if not p.startswith(QUOTE_NOT_FOUND)]
        (removed if problems else kept).append({**sentence, "problems": problems})
        if not problems:
            judgements.append(judgement)
    for sentence in r["removed"]:                                             # removed in the run: all checks
        problems = check_sentence(sentence, passages, index)
        if problems:
            removed.append({**sentence, "problems": problems})
            continue
        kept.append({**sentence, "problems": []})
        judgements.append(judge(sentence["text"], " ".join(passages[p]["text"] for p in sentence["sources"])))
        newly.append({"id": q["id"], "text": sentence["text"], "quote": sentence["quote"],
                      "passage": " ".join(passages[p]["text"] for p in sentence["sources"]),
                      "old_problems": sentence["problems"]})
    for sentence in kept:
        sentence["groundedness"] = round(groundedness(sentence["text"],
                                                      norm(" ".join(passages[p]["text"] for p in sentence["sources"]))), 3)
    false_by_sentence, n_cites = shown({"passages": list(passages.items()), "sentences": kept}, q, index)
    row = {**r, "support_score": support_score(kept, removed, passages, s), "n_kept": len(kept),
           "n_removed": len(removed), "removed": removed, "judgements": judgements,
           "sentences": [{"text": x["text"], "sources": x["sources"], "groundedness": x["groundedness"]} for x in kept],
           "fabrications_caught": count_fabrications(removed), "false_by_sentence": false_by_sentence,
           "citations_shown": n_cites, "reverified": True}
    return row, newly


def reverify(pairs, s, search, index, judge, shown):
    """search(question) -> (chosen 8, found 20); judge(sentence, passage text) -> yes/no/error;
    shown(r, q, index) -> (false citations by sentence, citations shown): the separate checker."""
    out = {"pairs": [], "search_changed": [], "newly_kept": [], "kept_despite_other_problem": [], "now_removed": []}
    for q, r in pairs:
        if r["status_raw"] == evaluate.ERROR or r["model_said"] != "SUPPORTED":
            out["pairs"].append((q, r))                                       # no draft to check again
            continue
        chosen, found = search(q["question"])
        # rule (1): the 8 passages sent to the model (their decisions and the best score; the run saved no chunk
        # ids). Passages 9-20 are not compared: two with the same score can swap (A027), and the model never saw them
        if ranked(chosen, found)[:len(chosen)] != r["ranked_decisions"][:len(chosen)] \
                or abs(max(p["score"] for p in chosen) - r["top_score"]) > 1e-4:
            out["pairs"].append((q, r))
            out["search_changed"].append(q["id"])
            continue
        row, newly = recheck(q, r, s, chosen, index, judge, shown)
        out["pairs"].append((q, row))
        if q["split"] == "tune" or q["tag"] == "adversarial":                 # only these are listed
            out["newly_kept"] += [{k: x[k] for k in ("id", "text", "quote", "passage")} for x in newly]
            out["kept_despite_other_problem"] += [x["id"] for x in newly
                                                  if any(not p.startswith(QUOTE_NOT_FOUND) for p in x["old_problems"])]
            out["now_removed"] += [{"id": q["id"], "text": x["text"], "problems": x["problems"]}
                                   for x in row["removed"] if x["text"] in {k["text"] for k in r["sentences"]}]
    return out


def pipeline_search(s):
    """The pipeline's search (app/pipeline.py answer, step 1), as in scripts/error_analysis.py."""
    from app.citations import CitationIndex
    from app.pipeline import named_decisions
    from app.search import Searcher
    searcher, index = Searcher(), CitationIndex()

    def search(question):
        ids = named_decisions(question, index) if s.get("case_filter") else []
        found = searcher.search(question, k=int(s["retrieve_k"]), decision_ids=ids) if ids else \
            searcher.search(question, k=int(s["retrieve_k"]))
        return searcher.choose(question, found, int(s["top_k"]), s["use_reranker"]), found
    return search, index


def main(argv):
    path = argv[0]
    saved = json.load(open(path))
    s = saved["settings"]
    search, index = pipeline_search(s)
    out = reverify(evaluate.load_run_file(path), s, search, index,
                   lambda text, passage: evaluate.judge_with_retry(text, passage, print), evaluate.check_shown_citations)
    tune = [p for p in out["pairs"] if p[0]["split"] == "tune" or p[0]["tag"] == "adversarial"]
    before = evaluate.metrics(evaluate.load_run_file(path), s, "tune")
    after = evaluate.metrics(tune, s, "tune")
    print(f"Search changed (rule 1, not rechecked): {out['search_changed'] or 'none'}")
    print(f"\n== Newly kept on TUNE + adversarial: {len(out['newly_kept'])} (rule 2: check each by hand) ==")
    for x in out["newly_kept"]:
        print(f"  {x['id']}  quote: \"{x['quote']}\"")
    print(f"\nKept although removed for another reason (rule 4, must be empty): {out['kept_despite_other_problem']}")
    print(f"Kept in the run, removed now: {len(out['now_removed'])}")
    for x in out["now_removed"]:
        print(f"  {x['id']}  {x['problems']}")
    print(f"\n  {'metric (TUNE + adversarial)':32} {'run 2':>10} {'rechecked':>10}")
    for k in after:
        print(f"  {k:32} {before[k]!s:>10} {after[k]!s:>10}")

    results = [{"question_id": q["id"], "tag": q["tag"], "split": q["split"], "result": r} for q, r in out["pairs"]]
    new = {**saved, "note": f"{saved['note']} | rechecked with the changed quote matching (step 8.2)",
           "tune_metrics": after, "tune_sweep": evaluate.sweep(tune, s, "tune"), "results": results,
           "recheck": {k: v for k, v in out.items() if k != "pairs"}}
    target = config.EVAL_DIR / "runs" / path.split("/")[-1].replace(".json", "_reverified.json")
    json.dump(new, open(target, "w"), indent=1)
    print(f"\nsaved {target}")


if __name__ == "__main__":
    main(sys.argv[1:])
