"""Saved answers to the example questions of the chat page (Dr. Salloum, 2026-11-13: show the jury
without spending tokens or waiting). Each example question is answered ONCE by the real pipeline,
with every check of the verifier, and stored exactly as the page shows it. /api/ask then returns the
stored answer, so the same question costs no search and no model call. Made again with
`python -m scripts.make_demo_answers` (for example after a change to the prompt or the data)."""
import json
import re
import time
from psycopg.types.json import Jsonb
from app import config, db
from app.pipeline import answer, ERROR

RETRIES = 6        # Groq's free tier allows 8,000 tokens a minute: several example questions in a row hit it (Joe, 2026-11-21)


def key(question):
    """The same question typed differently: case, spaces and the final ? . ! do not count."""
    return re.sub(r"\s+", " ", question).strip().rstrip("?.! ").lower()


def _json(value):
    return Jsonb(value, dumps=lambda v: json.dumps(v, default=str))    # dates as text


def answer_waiting(question, searcher, index, settings, log):
    """The pipeline's answer; on Groq's per-minute limit, waits the time Groq gives and asks again (the evaluation's
    rule, evaluate.rate_limit_wait). Not on the daily limit (hours away) or on any other error."""
    from app.evaluate import rate_limit_wait          # here: evaluate imports the pipeline too
    for attempt in range(RETRIES + 1):
        r = answer(question, searcher, index, settings)
        wait = rate_limit_wait(r["reason"]) if r["status"] == ERROR else None
        if wait is None or "per day" in r["reason"] or attempt == RETRIES:
            return r
        log(f"  rate limit: waiting {wait:.0f} s")
        time.sleep(wait)


def make_all(searcher, index, log=print):
    """Answers every example question with the real pipeline and saves it. Returns how many were saved.
    An ERROR (for example the model's daily limit) is not saved: the answer saved before is kept."""
    from app.api import public_answer                  # here, because app.api uses this module
    settings, saved = db.get_settings(), 0
    with db.connect() as con:                          # a question no longer in the examples is forgotten
        con.execute("DELETE FROM demo_answers WHERE NOT key = ANY(%s)",
                    ([key(q) for q in config.EXAMPLE_QUESTIONS],))
    for q in config.EXAMPLE_QUESTIONS:
        r = answer_waiting(q, searcher, index, settings, log)
        log(f"{r['status']:15} {len(r['shown_sentences'])} sentence(s)  {q}")
        if r["status"] == ERROR:
            log(f"  not saved: {r['reason']}")
            if "per day" in r["reason"]:                   # waiting will not help: stop, the saved answers stay
                log("  the model's daily limit is used up: run it again tomorrow")
                break
            continue
        with db.connect() as con:
            con.execute("""INSERT INTO demo_answers (key, question, result, shown) VALUES (%s, %s, %s, %s)
                           ON CONFLICT (key) DO UPDATE SET question = EXCLUDED.question, result = EXCLUDED.result,
                           shown = EXCLUDED.shown, saved_at = now()""",
                        (key(q), q, _json(r), _json(public_answer(r))))
        saved += 1
    return saved


def _row(question):
    with db.connect() as con:
        return con.execute("SELECT * FROM demo_answers WHERE key = %s", (key(question),)).fetchone()


def saved_answer(question):
    """The saved answer as the page shows it, marked demo, with its date; None if the question has none."""
    row = _row(question)
    if row is None:
        return None
    return {**row["shown"], "demo": True, "saved_at": row["saved_at"].isoformat()}


def saved_result(question):
    """The pipeline's result saved with the answer, as it is logged for each question (FR28)."""
    row = _row(question)
    if row is None:
        return None
    r = row["result"]
    return {**r, "question": question, "ms_search": 0, "ms_model": 0, "ms_total": 0,
            "reason": f"saved demo answer of {row['saved_at']:%Y-%m-%d}: {r['reason']}"}


def all_saved():
    with db.connect() as con:
        return con.execute("SELECT question, shown->>'status' AS status, saved_at FROM demo_answers "
                           "ORDER BY question").fetchall()
