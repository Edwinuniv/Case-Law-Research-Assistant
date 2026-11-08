"""WEEK 8, step 8.2 - Error analysis of a run, TUNE split only (SR29: TEST is reported once, with run_eval --test).
For every answerable question answered "not supported": the first cause in pipeline order (gate, model,
verifier, tau), the verifier's problems by kind, and whether the gold quote was in the 8 passages (if not,
the search failed before the model could answer). Also the unanswerable questions that were answered.
The saved results keep no passage text, so the gold quote is checked by running the run's search again
(search only, no model call; same data, same settings, same case filter).
Usage: python -m scripts.error_analysis RUN   (RUN = a database run id or eval/runs/<file>.json)
       -> eval/runs/error_analysis_<date>.json"""
import sys
import json
import datetime
from collections import Counter
from app import config, db, evaluate
from app.pipeline import NOT_SUPPORTED
from scripts.compare_runs import load


def cause(r, s):
    if r["top_score"] < s["min_retrieval"]:
        return "below the retrieval gate"
    if r["model_said"] != "SUPPORTED":
        return "the model said the passages do not answer"
    if r["n_kept"] == 0:
        return "every sentence removed by the verifier"
    return "support score under tau_abstain"


def analyse(pairs, s, quote_found):
    """quote_found(question) -> True / False (None if the question has no gold quote)."""
    tune = [(q, r) for q, r in pairs if q["split"] == "tune"]
    answerable = [(q, r) for q, r in tune if q["tag"] == "answerable"]
    quote = {q["id"]: quote_found(q) for q, _ in answerable}
    abstained = [(q, r) for q, r in answerable if evaluate.status_at(r, s) == NOT_SUPPORTED]
    problems = Counter(p.split(":")[0] for _, r in abstained for x in r.get("removed", []) for p in x["problems"])
    with_quote = [v for v in quote.values() if v is not None]
    return {"abstained_but_should_answer": [{"id": q["id"], "cause": cause(r, s), "support": r["support_score"],
                                             "gold_quote_in_8_passages": quote[q["id"]]} for q, r in abstained],
            "verifier_problems": dict(problems.most_common()),
            "answered_but_should_abstain": [{"id": q["id"], "status": evaluate.status_at(r, s),
                                             "support": r["support_score"]}
                                            for q, r in tune if q["tag"] == "unanswerable"
                                            and evaluate.status_at(r, s) != NOT_SUPPORTED],
            "quote@8": {"found": sum(with_quote), "of": len(with_quote)}}


def search_quote_check(s):
    """The pipeline's search (app/pipeline.py answer, step 1), copied so that the pipeline is not changed
    while run 2 is running."""
    from app.citations import CitationIndex
    from app.pipeline import named_decisions
    from app.search import Searcher
    from scripts.tune_search import norm
    searcher, index = Searcher(), CitationIndex()

    def quote_found(q):
        if not q.get("gold_quote"):
            return None
        ids = named_decisions(q["question"], index) if s.get("case_filter") else []
        found = searcher.search(q["question"], k=int(s["retrieve_k"]), decision_ids=ids) if ids else \
            searcher.search(q["question"], k=int(s["retrieve_k"]))
        chosen = searcher.choose(q["question"], found, int(s["top_k"]), s["use_reranker"])
        return any(norm(q["gold_quote"]) in norm(p["text"]) for p in chosen)
    return quote_found


def main(argv):
    s = db.get_settings()
    out = analyse(load(argv[0]), s, search_quote_check(s))
    print(f"Run {argv[0]}, TUNE split, tau_abstain {s['tau_abstain']}\n")
    print(f"== Answerable but answered 'not supported': {len(out['abstained_but_should_answer'])} ==")
    for kind, n in Counter(x["cause"] for x in out["abstained_but_should_answer"]).most_common():
        print(f"  {n:3}  {kind}")
    for x in out["abstained_but_should_answer"]:
        print(f"  {x['id']}  {x['cause']}  (support {x['support']}, gold quote in the 8 passages: "
              f"{x['gold_quote_in_8_passages']})")
    print("\n== Verifier problems in those answers ==")
    for kind, n in out["verifier_problems"].items():
        print(f"  {n:3}  {kind}")
    print(f"\n== Unanswerable but answered: {len(out['answered_but_should_abstain'])} ==")
    for x in out["answered_but_should_abstain"]:
        print(f"  {x['id']}  {x['status']}  (support {x['support']})")
    print(f"\nGold quote in the 8 passages: {out['quote@8']['found']} of {out['quote@8']['of']} answerable questions")

    date = datetime.datetime.now().isoformat(timespec="seconds")
    (config.EVAL_DIR / "runs").mkdir(exist_ok=True)
    path = config.EVAL_DIR / "runs" / f"error_analysis_{date.replace(':', '-')}.json"
    json.dump({"date": date, "run": argv[0], "split": "tune", "tau_abstain": s["tau_abstain"], **out},
              open(path, "w"), indent=1)
    print(f"saved {path}")


if __name__ == "__main__":
    main(sys.argv[1:])
