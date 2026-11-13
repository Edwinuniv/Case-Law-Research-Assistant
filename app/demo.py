"""Saved answers to the example questions of the chat page (Dr. Salloum, 2026-11-13: show the jury
without spending tokens or waiting). Each example question is answered ONCE by the real pipeline,
with every check of the verifier, and stored exactly as the page shows it. /api/ask then returns the
stored answer, so the same question costs no search and no model call. Made again with
`python -m scripts.make_demo_answers` (for example after a change to the prompt or the data)."""
import json
import re
from psycopg.types.json import Jsonb
from app import config, db
from app.pipeline import answer, ERROR


def key(question):
    """The same question typed differently: case, spaces and the final ? . ! do not count."""
    return re.sub(r"\s+", " ", question).strip().rstrip("?.! ").lower()


def _json(value):
    return Jsonb(value, dumps=lambda v: json.dumps(v, default=str))    # dates as text


def make_all(searcher, index, log=print):
    """Answers every example question with the real pipeline and saves it. Returns how many were saved.
    An ERROR (for example the model's daily limit) is not saved: the answer saved before is kept."""
    from app.api import public_answer                  # here, because app.api uses this module
    settings, saved = db.get_settings(), 0
    with db.connect() as con:                          # a question no longer in the examples is forgotten
        con.execute("DELETE FROM demo_answers WHERE NOT key = ANY(%s)",
                    ([key(q) for q in config.EXAMPLE_QUESTIONS],))
    for q in config.EXAMPLE_QUESTIONS:
        r = answer(q, searcher, index, settings)
        log(f"{r['status']:15} {len(r['shown_sentences'])} sentence(s)  {q}")
        if r["status"] == ERROR:
            log(f"  not saved: {r['reason']}")
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
