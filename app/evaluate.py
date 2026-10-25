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


# ---------------- running ----------------
def run_evaluation(searcher, index, trigger="manual", note="", judge=True, log=print):
    settings = db.get_settings()
    with db.connect() as con:
        run_id = con.execute("INSERT INTO eval_runs (trigger, status, settings, note) VALUES (%s, 'running', %s, %s) "
                             "RETURNING id", (trigger, Jsonb(settings), note)).fetchone()["id"]
    questions = load_questions()
    for n, q in enumerate(questions, 1):
        r = answer(q["question"], searcher, index, settings, skip_gate=True)
        false_by_sentence, n_cites = check_shown_citations(r, q, index)
        judgements = []
        if judge and r["status"] != ERROR:
            passages = dict(r["passages"])
            for s in r["sentences"]:
                try:
                    judgements.append(llm.judge_support(s["text"], " ".join(passages[p]["text"] for p in s["sources"])))
                except llm.ModelError:
                    judgements.append("error")
        chosen = [p["decision_id"] for _, p in r["passages"]]
        row = {"top_score": r["top_score"], "support_score": r["support_score"], "status_raw": r["status"],
               "model_said": r["model_said"], "reason": r["reason"],
               "n_kept": len(r["sentences"]), "n_removed": len(r["removed"]),
               "ranked_decisions": chosen + [d for d in r["retrieved_decisions"] if d not in chosen],
               "sentences": [{"text": s["text"], "sources": s["sources"], "groundedness": s["groundedness"]}
                             for s in r["sentences"]],
               "removed": r["removed"], "fabrications_caught": r["fabrications_caught"],
               "false_by_sentence": false_by_sentence, "citations_shown": n_cites,
               "judgements": judgements, "ms_total": r["ms_total"]}
        with db.connect() as con:
            con.execute("INSERT INTO eval_results (run_id, question_id, tag, split, result) VALUES (%s,%s,%s,%s,%s)",
                        (run_id, q["id"], q["tag"], q["split"], Jsonb(row)))
        log(f"[{n}/{len(questions)}] {q['id']} ({q['tag']}) -> {r['status']} support={r['support_score']}")
    with db.connect() as con:
        con.execute("UPDATE eval_runs SET status = 'done' WHERE id = %s", (run_id,))
    return run_id


def load_run(run_id):
    questions = {q["id"]: q for q in load_questions()}
    with db.connect() as con:
        rows = con.execute("SELECT * FROM eval_results WHERE run_id = %s ORDER BY question_id", (run_id,)).fetchall()
    return [(questions.get(r["question_id"], {"id": r["question_id"], "tag": r["tag"], "split": r["split"],
                                              "question": "(deleted question)", "gold_decision_ids": []}),
             r["result"]) for r in rows]
