"""Measure the follow-up pairs of followups-v1 (EVALUATION.md, "Follow-up questions rule"; Edwin, 2026-11-20).
For each pair: the first question is answered on its own, then the follow-up is asked with that answer as the chat
history (pipeline.turn_of, as on the website). Only the follow-up is scored, with the same row and the same separate
checker as an eval-v1 question (evaluate.result_row); the first answer's status is kept for context.
TUNE pairs only while deciding; the TEST pairs once, with --test, after the decision.
Saved after every pair in eval/runs/followups_<split>_<date>.json; at Groq's daily limit the run pauses and
continues later with --resume FILE, which refuses if the settings changed in between.
Usage: python -m scripts.run_followups                 -> TUNE pairs, then the metrics and the rule's verdict
       python -m scripts.run_followups --test          -> TEST pairs, ONCE, after the decision on TUNE
       python -m scripts.run_followups --resume FILE   -> continue a paused run
       python -m scripts.run_followups --report FILE   -> the metrics of a saved run again"""
import datetime
import json
import sys
from pathlib import Path
from app import config, db, evaluate
from app.pipeline import ERROR, NOT_SUPPORTED, turn_of

PAIRS = config.ROOT / "eval" / "followups.jsonl"
RUNS = config.ROOT / "eval" / "runs"
FORBIDDEN = "forbidden text shown:"


def read_pairs(path=PAIRS):
    return [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]


def select(pairs, split):
    """The pairs of one split; adversarial pairs too only if they belong to it (the rule: tune pairs only)."""
    return [p for p in pairs if p["split"] == split]


def as_question(p):
    """The follow-up as an evaluation question: its own tag, gold decisions and forbidden strings."""
    return {"id": p["id"], "tag": p["tag"], "split": p["split"], "question": p["follow_up"],
            "gold_decision_ids": p.get("gold_decision_ids") or [], "must_not_appear": p.get("must_not_appear") or []}


def measure(p, searcher, index, s, judge, log):
    """One pair: the first answer, then the follow-up with the chat so far. Returns the follow-up's row."""
    first = evaluate.answer_with_retry(p["first_question"], searcher, index, s, log)
    turn = turn_of(first)
    if turn is None:                                     # no chat to follow: never asked as an independent question
        return {"first_status": first["status"], "status_raw": ERROR, "reason": "the first answer failed",
                "top_score": 0, "support_score": 0, "model_said": "", "n_kept": 0, "n_removed": 0,
                "ranked_decisions": [], "sentences": [], "removed": [], "fabrications_caught": 0,
                "false_by_sentence": [], "citations_shown": 0, "judgements": [], "ms_total": first["ms_total"],
                "tokens": first.get("tokens", {})}
    r = evaluate.answer_with_retry(p["follow_up"], searcher, index, s, log, history=[turn])
    judgements = evaluate.judge_sentences(r, log) if judge and r["status"] != ERROR else []
    return {"first_status": first["status"], **evaluate.result_row(r, as_question(p), index, judgements)}


def save(out, data):
    out.write_text(json.dumps(data, indent=1, ensure_ascii=False, default=str), encoding="utf-8")


def run(pairs, searcher, index, s, out, judge=True, log=print, resume=False, split="tune"):
    """Measures the pairs not done yet, saving after each one. Returns "done" or "paused"."""
    out = Path(out)
    if resume:
        data = json.loads(out.read_text(encoding="utf-8"))
        changed = sorted(k for k in set(s) | set(data["settings"]) if s.get(k) != data["settings"].get(k))
        if changed:
            raise ValueError(f"settings changed since this run started: {', '.join(changed)}")
    else:
        data = {"date": datetime.datetime.now().isoformat(timespec="seconds"), "pairs_file": "followups-v1",
                "split": split, "settings": s, "status": "running", "pairs": {}}
    for p in [p for p in pairs if p["id"] not in data["pairs"]]:
        try:
            row = measure(p, searcher, index, s, judge, log)
        except evaluate.DailyLimit as e:                  # nothing saved for this pair: it is asked again
            data["status"] = "paused"
            save(out, data)
            log(f"Paused at {p['id']} ({len(data['pairs'])} pairs done): {e}")
            return "paused"
        data["pairs"][p["id"]] = {"tag": p["tag"], "split": p["split"], "kind": p["kind"],
                                  "gold_decision_ids": p.get("gold_decision_ids") or [], **row}
        save(out, data)
        log(f"{p['id']} ({p['tag']}, {p['kind']}): first {row['first_status']} -> follow-up {row['status_raw']}")
    data["status"] = "done"
    save(out, data)
    return "done"


def load(path):
    """A saved run as (question, row) pairs, the shape evaluate.metrics reads (the file holds all it needs)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [({"id": pid, "tag": row["tag"], "split": row["split"], "gold_decision_ids": row["gold_decision_ids"]}, row)
            for pid, row in data["pairs"].items()]


def shown(pairs, s):
    return [(q, r) for q, r in pairs if evaluate.status_at(r, s) not in (NOT_SUPPORTED, ERROR)]


def forbidden_shown(pairs, s):
    """Forbidden strings in the sentences a visitor would see (rule condition 2)."""
    return sum(1 for _, r in shown(pairs, s) for problems in r["false_by_sentence"] for x in problems
               if x.startswith(FORBIDDEN))


def measures(pairs, s):
    """evaluate.metrics on the follow-ups, with forbidden text counted apart from false citations."""
    m = evaluate.metrics(pairs, s)
    m["forbidden_text_shown"] = forbidden_shown(pairs, s)
    m["false_citations_shown"] -= m["forbidden_text_shown"]          # metrics counts both as problems
    m["first_answer_errors"] = sum(1 for _, r in pairs if r.get("first_status") == ERROR)
    return m


def verdict(m):
    """The rule's three measured conditions (condition 4, independent questions unchanged, is proved by tests)."""
    c1 = m["false_citations_shown"] == 0
    c2 = m["forbidden_text_shown"] == 0
    c3 = all(m.get(k) is not None and m[k] >= 0.80 for k in ("abstention_precision", "abstention_recall"))
    if c1 and c2 and c3:
        note = "all conditions hold: follow-ups may be switched on, then the TEST pairs are reported once"
    elif c1 and c2:
        note = "only abstention below 0.80: follow-ups stay off, the numbers are reported"
    else:
        note = "a false citation or forbidden text was shown: follow-ups stay off"
    return {"1_no_false_citation": c1, "2_no_forbidden_text": c2, "3_abstention_at_least_0.80": c3,
            "switch_on": c1 and c2 and c3, "note": note}


def report(path, s):
    pairs = load(path)
    m = measures(pairs, s)
    print(f"\n== follow-ups, {pairs[0][0]['split'] if pairs else '?'} split ({len(pairs)} pairs) ==")
    for k, v in m.items():
        print(f"  {k:32} {v}")
    print("\n  rule (EVALUATION.md):")
    for k, v in verdict(m).items():
        print(f"  {k:32} {v}")


def main(argv):
    s = db.get_settings()
    if argv[:1] in (["--resume"], ["--report"]):
        out = Path(argv[1])
        if argv[0] == "--report":
            return report(out, s)
        split = json.loads(out.read_text(encoding="utf-8"))["split"]
    else:
        split = "test" if argv[:1] == ["--test"] else "tune"
        out = RUNS / f"followups_{split}_{datetime.datetime.now():%Y-%m-%dT%H-%M-%S}.json"
    from app.citations import CitationIndex
    from app.search import Searcher
    status = run(select(read_pairs(), split), Searcher(), CitationIndex(), s, out, resume=argv[:1] == ["--resume"],
                 split=split)
    if status == "paused":
        print(f"\nPaused at the model provider's daily limit. Continue later with:\n"
              f"    python -m scripts.run_followups --resume {out}")
        return
    report(out, s)


if __name__ == "__main__":
    main(sys.argv[1:])
