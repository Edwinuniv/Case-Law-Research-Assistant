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


# ---------------- the separate false-citation checker (SR38, FR16) ----------------
def check_shown_citations(r, q, index):
    """Independent of verify.py: for every kept sentence, re-check (a) the citations OUR CODE renders,
    (b) any citation written in the text, using the citation table AND the citation map,
    (c) the forbidden strings of adversarial questions. Returns per-sentence lists of problems."""
    passages = dict(r["passages"])
    retrieved = {p["decision_id"] for p in passages.values()}
    per_sentence, citations_shown = [], 0
    with db.connect() as con:
        for s in r["sentences"]:
            problems = []
            cited = [passages[p] for p in s["sources"] if p in passages]
            for p in cited:                                                      # (a) rendered citations
                d = con.execute("SELECT citations FROM decisions WHERE decision_id = %s",
                                (p["decision_id"],)).fetchone()
                for c in (d["citations"] if d else [])[:1]:
                    citations_shown += 1
                    cluster = index.cluster_for(c)
                    if cluster is None or index.decision_for_cluster(cluster) != p["decision_id"]:
                        problems.append(f"rendered citation does not match: {c}")
            opinions = [p["opinion_id"] for p in cited]
            for c in find_citations(s["text"]):                                  # (b) citations in the text
                citations_shown += 1
                cluster = index.cluster_for(c)
                if cluster is None:
                    problems.append(f"citation does not exist: {c}")
                    continue
                in_map = con.execute("SELECT 1 FROM citation_map WHERE citing_opinion_id = ANY(%s) "
                                     "AND cited_cluster_id = %s LIMIT 1", (opinions, cluster)).fetchone()
                if index.decision_for_cluster(cluster) not in retrieved and not in_map:
                    problems.append(f"citation not from a retrieved opinion or its citation map: {c}")
            for bad in q.get("must_not_appear") or []:                           # (c) forbidden strings
                if bad and bad.lower() in s["text"].lower():
                    problems.append(f"forbidden text shown: {bad}")
            per_sentence.append(problems)
    return per_sentence, citations_shown
