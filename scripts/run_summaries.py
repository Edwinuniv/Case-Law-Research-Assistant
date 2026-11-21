"""Measure the passage summaries on summaries-v1 (EVALUATION.md, "Passage summaries"; Edwin, 2026-11-21).
For each request: its TUNE question is answered first, as on the website (no evaluation shortcut), then the request is
sent with that answer as the chat's last answer (pipeline.turn_of). Every shown line is checked by the same separate
checker as eval-v1 (evaluate.check_shown_citations). Saved after every request; at Groq's daily limit the run pauses
and continues with --resume.
Conditions read automatically: (1) 0 false citations shown, (2) every shown line cites only a passage sent, (3) at
least 12 of the 14 requests shown. Condition (4) is Edwin's reading of the report (the picks give each passage's point).
Usage: python -m scripts.run_summaries                  -> eval/runs/summaries_run3.json + _report.txt (runs 1-2: summaries_run1.*, _run2.*)
       python -m scripts.run_summaries --resume         -> continue the same file after the daily limit
       python -m scripts.run_summaries --report         -> the report again"""
import json
import sys
import time
from app import config, db, evaluate
from app.pipeline import ANSWERED, ERROR, LOW_CONFIDENCE, answer, label_of, turn_of

SET = config.ROOT / "eval" / "summaries.jsonl"
RUN = config.ROOT / "eval" / "runs" / "summaries_run3.json"   # run 1 failed (1), run 2 failed (4); EVALUATION.md
SETTINGS_FOR_RUN = {"passage_summaries": True, "prompt_version": "v2", "tau_abstain": 0.20}   # the rule's settings
RETRIES = 6


class DailyLimit(Exception):
    """Groq's daily limit: the run pauses; --resume continues it."""


def with_retry(call, log):
    """The pipeline's result; waits Groq's per-minute limit (the evaluation's rule); raises DailyLimit at the daily one."""
    for attempt in range(RETRIES + 1):
        r = call()
        wait = evaluate.rate_limit_wait(r["reason"]) if r["status"] == ERROR else None
        if wait is not None and "per day" in r["reason"]:
            raise DailyLimit(r["reason"])
        if wait is None or attempt == RETRIES:
            return r
        log(f"   rate limit: waiting {wait:.0f} s")
        time.sleep(wait)


def run_one(item, searcher, index, settings, checker=evaluate.check_shown_citations, log=print):
    first = with_retry(lambda: answer(item["first"], searcher, index, settings), log)
    turn = turn_of(first)
    r = with_retry(lambda: answer(item["request"], searcher, index, settings, previous=turn), log)
    false_by_line, n_cites = checker({"passages": r["passages"], "sentences": r["shown_sentences"]},
                                     {"must_not_appear": []}, index)
    return {"id": item["id"], "kind": item["kind"], "first": item["first"], "first_status": first["status"],
            "request": item["request"], "status": r["status"], "reason": r["reason"],
            "sent": [{"pid": pid, "chunk_id": p["chunk_id"], "decision_id": p["decision_id"], "case": p["case_name"],
                      "label": label_of(p), "score": p.get("score")} for pid, p in r["passages"]],
            "shown": [{"text": s["text"], "sources": s["sources"]} for s in r["shown_sentences"]],
            "removed": [{"text": s["text"], "sources": s["sources"], "problems": s["problems"]} for s in r["removed"]],
            "false_citations": sum(1 for problems in false_by_line if problems), "citations_shown": n_cites,
            "tokens": r.get("tokens")}


def run_all(items, searcher, index, path, settings=None, checker=evaluate.check_shown_citations, log=print,
            on_row=lambda row: None):
    """Runs the requests not yet in `path`, saving after each one."""
    saved = json.loads(path.read_text()) if path.exists() else {"settings": settings, "rows": []}
    settings = saved["settings"] or settings
    done = {row["id"] for row in saved["rows"]}
    path.write_text(json.dumps(saved, indent=1))
    for item in items:
        if item["id"] in done:
            continue
        log(f"{item['id']}  {item['request']}  (after {item['first_id']})")
        row = run_one(item, searcher, index, settings, checker, log)
        saved["rows"].append(row)
        path.write_text(json.dumps(saved, indent=1))
        on_row(row)
    return saved


def verdict(rows):
    shown_rows = [r for r in rows if r["status"] in (ANSWERED, LOW_CONFIDENCE) and r["shown"]]
    lines = [(line, {s["pid"] for s in r["sent"]}) for r in rows for line in r["shown"]]
    inside = sum(1 for line, sent in lines if set(line["sources"]) <= sent)
    v = {"requests": len(rows), "shown": len(shown_rows), "false_citations": sum(r["false_citations"] for r in rows),
         "citations_shown": sum(r["citations_shown"] for r in rows), "lines_shown": len(lines),
         "only_requested": inside / len(lines) if lines else 1.0}
    v["automatic_conditions_hold"] = v["false_citations"] == 0 and v["only_requested"] == 1.0 and v["shown"] >= 12
    return v


def report(saved):
    out = [f"Passage summaries, summaries-v1 ({len(saved['rows'])} of 14 requests), settings {saved['settings']}", ""]
    for r in saved["rows"]:
        out.append(f"{r['id']} [{r['kind']}] {r['request']!r} after {r['first']!r} (first answer {r['first_status']})")
        out.append(f"   -> {r['status']}  {r['reason']}")
        out.append("   sent: " + ", ".join(f"{s['pid']} {s['case'][:30]} - {s['label']}" for s in r["sent"]))
        out += [f"   SHOWN   {line['text']}" for line in r["shown"]]
        out += [f"   removed {line['text'][:120]}  ({line['problems'][0]})" for line in r["removed"]]
        out.append("")
    v = verdict(saved["rows"])
    out.append(f"(1) false citations shown: {v['false_citations']} of {v['citations_shown']}")
    out.append(f"(2) lines citing only a passage sent: {v['only_requested']:.0%} of {v['lines_shown']}")
    out.append(f"(3) requests shown: {v['shown']} of {v['requests']} (12 needed)")
    out.append(f"(1)-(3) hold: {v['automatic_conditions_hold']}.  (4): Edwin reads the SHOWN lines above.")
    return "\n".join(out)


def main(argv):
    items = [json.loads(line) for line in open(SET, encoding="utf-8") if line.strip()]
    if "--report" not in argv:
        if RUN.exists() and "--resume" not in argv:
            raise SystemExit(f"{RUN} exists: use --resume to continue it, or --report.")
        from app.citations import CitationIndex
        from app.search import Searcher
        settings = dict(db.get_settings(), **SETTINGS_FOR_RUN)
        try:
            run_all(items, Searcher(), CitationIndex(), RUN, settings)
        except DailyLimit as e:
            print(f"Paused at Groq's daily limit ({e}). Run again tomorrow with --resume.")
            return
    text = report(json.loads(RUN.read_text()))
    RUN.with_name(RUN.stem + "_report.txt").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main(sys.argv[1:])
