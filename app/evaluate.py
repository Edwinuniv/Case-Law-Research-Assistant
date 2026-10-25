"""Evaluation: test questions, runs, the separate false-citation checker, metrics, sweep, comparison."""
import json
from psycopg.types.json import Jsonb
from app import config, db, llm
from app.citations import find_citations
from app.pipeline import answer, decide, ANSWERED, LOW_CONFIDENCE, NOT_SUPPORTED, ERROR

QUESTION_FIELDS = ["id", "tag", "split", "question", "expected_answer", "gold_decision_ids",
                   "gold_quote", "must_not_appear", "why", "author"]


# ---------------- test questions (stored in the database, exported to git) ----------------
def import_questions(path=None):
    path = path or config.EVAL_DIR / "questions.jsonl"
    n = 0
    with db.connect() as con:
        for line in open(path):
            if not line.strip():
                continue
            q = {k: v for k, v in json.loads(line).items() if k in QUESTION_FIELDS}
            q.setdefault("gold_decision_ids", []); q.setdefault("must_not_appear", [])
            q.setdefault("split", "tune")
            cols = list(q)
            con.execute(f"INSERT INTO test_questions ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) "
                        f"ON CONFLICT (id) DO UPDATE SET " + ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c != "id"),
                        [q[c] for c in cols])
            n += 1
    return n


def load_questions():
    with db.connect() as con:
        return con.execute("SELECT * FROM test_questions ORDER BY id").fetchall()


def export_questions():
    return "".join(json.dumps({k: q[k] for k in QUESTION_FIELDS}) + "\n" for q in load_questions())


def expected(q):
    return "answer" if q["tag"] == "answerable" else "abstain"
