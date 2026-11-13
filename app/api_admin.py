"""JSON API for the React admin pages (step 5.9). Same work as the old Jinja admin pages (guide pp. 56-62, removed in step 5.10).
EVERY route here is protected by the router itself: CSRF on POST and the admin role checked in the
database at each request (SR35, NFR8). A route cannot be added here without that protection."""
import datetime
import threading
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel
from app import api, db, evaluate, logs

router = APIRouter(prefix="/api/admin",
                   dependencies=[Depends(api.check_csrf), Depends(api.require_admin)])


def run_in_background(kind, work):
    """Long work (evaluation, re-index) runs in a thread; its progress is saved in the jobs table."""
    job_id = db.start_job(kind)

    def target():
        try:
            db.end_job(job_id, "done", str(work() or ""))
        except Exception as e:
            db.end_job(job_id, "failed", f"{type(e).__name__}: {e}")
    threading.Thread(target=target, daemon=True).start()
    return job_id


def latest_run_id():
    with db.connect() as con:
        last = con.execute("SELECT id FROM eval_runs WHERE status = 'done' ORDER BY id DESC LIMIT 1").fetchone()
    return last["id"] if last else None


# ---------------- which split the admin pages show by default ----------------
# Thresholds are chosen on the TUNE split; the TEST split is reported once, at the end (EVALUATION.md, SR29).
# So every admin page shows TUNE unless the admin asks for test (the run page has a selector).
DEFAULT_SPLIT = "tune"


# ---------------- overview ----------------
@router.get("/home")
def home():
    s = db.get_settings()
    with db.connect() as con:
        counts = con.execute("""SELECT (SELECT count(*) FROM decisions) AS decisions,
            (SELECT count(*) FROM opinions) AS opinions, (SELECT count(*) FROM chunks) AS chunks,
            (SELECT count(*) FROM citations) AS citations, (SELECT count(*) FROM citation_map) AS citation_map,
            (SELECT count(*) FROM test_questions) AS questions,
            (SELECT count(*) FROM query_log WHERE created_at::date = now()::date) AS queries_today""").fetchone()
        jobs = con.execute("SELECT * FROM jobs ORDER BY id DESC LIMIT 6").fetchall()
    last = latest_run_id()
    m = evaluate.metrics(evaluate.load_run(last), s, DEFAULT_SPLIT) if last else None
    return {"counts": counts, "last_run": last, "metrics": m, "jobs": jobs,
            "chunk_max_words": s.get("chunk_max_words", 350)}


# ---------------- settings (FR23: preview on the latest run BEFORE saving) ----------------
PREVIEW_KEYS = ["abstention_precision", "abstention_recall", "answered_but_should_abstain",
                "abstained_but_should_answer", "low_confidence", "false_citations_shown"]


@router.get("/settings")
def settings():
    return db.get_settings()


@router.get("/settings/preview")
def settings_preview(tau_abstain: float, tau_confident: float, min_retrieval: float):
    """What the latest evaluation run would give with these thresholds. Saves nothing."""
    s = db.get_settings()
    last = latest_run_id()
    if not last:
        raise HTTPException(404, "No evaluation run yet: run one first.")
    new = dict(s, tau_abstain=tau_abstain, tau_confident=max(tau_confident, tau_abstain), min_retrieval=min_retrieval)
    pairs = evaluate.load_run(last)
    now, then = evaluate.metrics(pairs, s, DEFAULT_SPLIT), evaluate.metrics(pairs, new, DEFAULT_SPLIT)
    return {"run": last, "split": DEFAULT_SPLIT, "rows": [{"metric": k, "now": now.get(k), "then": then.get(k)} for k in PREVIEW_KEYS]}


class Settings(BaseModel):
    tau_abstain: float
    tau_confident: float
    min_retrieval: float
    top_k: int
    retrieve_k: int
    use_reranker: bool


@router.post("/settings")
def settings_save(body: Settings):
    """The same limits as the old Jinja page: tau_confident >= tau_abstain, 8-50 passages searched, 1-10 sent."""
    db.set_setting("tau_abstain", body.tau_abstain)
    db.set_setting("tau_confident", max(body.tau_confident, body.tau_abstain))
    db.set_setting("min_retrieval", body.min_retrieval)
    db.set_setting("retrieve_k", max(8, min(body.retrieve_k, 50)))
    db.set_setting("top_k", max(1, min(body.top_k, 10)))
    db.set_setting("use_reranker", body.use_reranker)
    return db.get_settings()


# ---------------- evaluation (FR13-FR20) ----------------
@router.get("/eval")
def eval_runs():
    s = db.get_settings()
    with db.connect() as con:
        runs = con.execute("SELECT * FROM eval_runs ORDER BY id DESC").fetchall()
    return [{**run, "metrics": evaluate.metrics(evaluate.load_run(run["id"]), s, DEFAULT_SPLIT) if run["status"] == "done" else {}}
            for run in runs]


class RunNote(BaseModel):
    note: str = ""


@router.post("/eval/run")
def eval_run(body: RunNote):
    if api.STATE["searcher"] is None:
        raise HTTPException(503, "The search index is not ready yet.")
    job = run_in_background("evaluation", lambda: f"run {evaluate.run_evaluation(api.STATE['searcher'], api.STATE['index'], 'manual', body.note, log=lambda *a: None)}")
    return {"job": job}


@router.get("/eval/compare")          # before /eval/{run_id}, or "compare" would be read as a run id
def eval_compare(a: int, b: int, split: str = DEFAULT_SPLIT):
    """Before / after on the same questions (the week-10 improvement); worse metrics are flagged (SR40)."""
    rows, flips = evaluate.compare(a, b, db.get_settings(), split or None)
    return {"a": a, "b": b, "split": split, "rows": rows, "flips": flips}


@router.get("/eval/{run_id}")
def eval_detail(run_id: int, split: str = DEFAULT_SPLIT, tau: float | None = None):
    """One run: metrics, threshold sweep (tune split) and every question, wrong outcomes first.
    tau = a what-if abstention threshold; it does not change the live system."""
    s = db.get_settings()
    if tau is not None:
        s = dict(s, tau_abstain=tau, tau_confident=max(tau, s["tau_confident"]))
    pairs = evaluate.load_run(run_id)
    if not pairs:
        raise HTTPException(404, "No such evaluation run.")
    table = []
    for q, res in pairs:
        st = evaluate.status_at(res, s)
        ok = (st == "NOT_SUPPORTED") == (q["tag"] != "answerable")
        false = sum(len(x) for x in res["false_by_sentence"]) if st in ("ANSWERED", "LOW_CONFIDENCE") else 0
        table.append({"id": q["id"], "tag": q["tag"], "split": q["split"], "question": q["question"],
                      "status": st, "ok": ok, "false": false, "support_score": res["support_score"],
                      "n_removed": res["n_removed"], "fabrications_caught": res["fabrications_caught"],
                      "removed": res.get("removed", []), "judgements": res.get("judgements", [])})
    table.sort(key=lambda t: (t["ok"], t["id"]))
    return {"run_id": run_id, "split": split, "tau_abstain": s["tau_abstain"], "table": table,
            "metrics": evaluate.metrics(pairs, s, split or None), "sweep": evaluate.sweep(pairs, s, "tune")}


# ---------------- test questions (FR13a-c) ----------------
TAGS, SPLITS = ("answerable", "unanswerable", "adversarial"), ("tune", "test")


@router.get("/questions")
def questions(tag: str = ""):
    return [q for q in evaluate.load_questions() if not tag or q["tag"] == tag]


@router.get("/questions/export")      # before /questions/{qid}
def questions_export():
    """The questions as eval/questions.jsonl, to commit in git (the evaluation set is versioned)."""
    return PlainTextResponse(evaluate.export_questions(), media_type="application/x-ndjson",
                             headers={"Content-Disposition": "attachment; filename=questions.jsonl"})


@router.get("/questions/{qid}")
def question(qid: str):
    q = next((x for x in evaluate.load_questions() if x["id"] == qid), None)
    if q is None:
        raise HTTPException(404, "No such question.")
    return q


class TestQuestion(BaseModel):
    id: str
    tag: str
    split: str
    question: str
    expected_answer: str = ""
    gold_decision_ids: list[int] = []
    gold_quote: str = ""
    must_not_appear: list[str] = []
    why: str = ""
    author: str = ""


@router.post("/questions")
def question_save(q: TestQuestion):
    """Adds a question or changes one (same SQL as the old Jinja page)."""
    if not q.id.strip() or not q.question.strip():
        raise HTTPException(400, "The ID and the question are required.")
    if q.tag not in TAGS or q.split not in SPLITS:
        raise HTTPException(400, f"Tag must be one of {', '.join(TAGS)}; split must be tune or test.")
    with db.connect() as con:
        con.execute("""INSERT INTO test_questions (id, tag, split, question, expected_answer, gold_decision_ids,
            gold_quote, must_not_appear, why, author, updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())
            ON CONFLICT (id) DO UPDATE SET tag = EXCLUDED.tag, split = EXCLUDED.split, question = EXCLUDED.question,
            expected_answer = EXCLUDED.expected_answer, gold_decision_ids = EXCLUDED.gold_decision_ids,
            gold_quote = EXCLUDED.gold_quote, must_not_appear = EXCLUDED.must_not_appear, why = EXCLUDED.why,
            author = EXCLUDED.author, updated_at = now()""",
                    (q.id.strip(), q.tag, q.split, q.question, q.expected_answer, q.gold_decision_ids, q.gold_quote,
                     [x.strip() for x in q.must_not_appear if x.strip()], q.why, q.author))
    return question(q.id.strip())


# ---------------- abstentions / failures (FR22, SR43) ----------------
STATUSES = ("NOT_SUPPORTED", "LOW_CONFIDENCE", "ERROR")
LABELS = ("correct", "should have answered", "add as unanswerable test question", "add as answerable test question")


@router.get("/abstentions")
def abstentions(status: str = "NOT_SUPPORTED"):
    """The questions the system did not answer confidently, with their passages and removed sentences.
    Who asked is NOT sent (the admin does not need it to tune abstention)."""
    if status not in STATUSES:
        raise HTTPException(400, "Unknown status.")
    with db.connect() as con:
        rows = con.execute("""SELECT id, created_at, question, status, reason, support_score, top_score, label, details
                              FROM query_log WHERE status = %s ORDER BY id DESC LIMIT 200""", (status,)).fetchall()
        ids = [cid for row in rows for _, cid, _ in (row["details"] or {}).get("passages", [])]
        chunks = {c["chunk_id"]: c for c in con.execute(
            "SELECT c.chunk_id, d.case_name, o.label FROM chunks c JOIN opinions o USING (opinion_id) "
            "JOIN decisions d ON d.decision_id = c.decision_id WHERE c.chunk_id = ANY(%s)", (ids,)).fetchall()}
    out = []
    for row in rows:
        d = row.pop("details") or {}
        row["passages"] = [{"chunk_id": cid, "score": score, "case_name": chunks.get(cid, {}).get("case_name"),
                            "label": chunks.get(cid, {}).get("label")} for _, cid, score in d.get("passages", [])]
        row["removed"] = d.get("removed", [])
        out.append(row)
    return out


class Label(BaseModel):
    label: str


@router.post("/abstentions/{log_id}/label")
def abstention_label(log_id: int, body: Label):
    """Marks one case. 'add as ...' also returns the question and tag to prefill a new test question (SR43)."""
    if body.label not in LABELS:
        raise HTTPException(400, "Unknown label.")
    with db.connect() as con:
        q = con.execute("UPDATE query_log SET label = %s WHERE id = %s RETURNING question", (body.label, log_id)).fetchone()
    if not q:
        raise HTTPException(404, "No such question in the log.")
    if body.label.startswith("add as"):
        return {"prefill": {"question": q["question"],
                            "tag": "unanswerable" if "unanswerable" in body.label else "answerable"}}
    return {"ok": True}


# ---------------- analytics (FR24-FR27, SR42) ----------------
@router.get("/analytics")
def analytics(start: datetime.date | None = None, end: datetime.date | None = None):
    """Per day: queries by result, median and 95th percentile response time, failure rate;
    and the questions it could not answer. Default: the last 30 days."""
    end = end or datetime.date.today()
    start = start or end - datetime.timedelta(days=30)
    with db.connect() as con:
        days = con.execute("""SELECT created_at::date AS day, count(*) AS n,
              percentile_cont(0.5) WITHIN GROUP (ORDER BY ms_total) AS p50,
              percentile_cont(0.95) WITHIN GROUP (ORDER BY ms_total) AS p95,
              avg((status = 'ERROR')::int) AS failure_rate,
              sum((status = 'ANSWERED')::int) AS answered, sum((status = 'LOW_CONFIDENCE')::int) AS low,
              sum((status = 'NOT_SUPPORTED')::int) AS not_supported, sum((status = 'ERROR')::int) AS errors
              FROM query_log WHERE created_at::date BETWEEN %s AND %s GROUP BY 1 ORDER BY 1""",
                           (start, end)).fetchall()
        unanswered = con.execute("""SELECT created_at, question, reason FROM query_log
              WHERE status = 'NOT_SUPPORTED' AND created_at::date BETWEEN %s AND %s
              ORDER BY id DESC LIMIT 50""", (start, end)).fetchall()
    days = [{k: (str(v) if k == "day" else float(v or 0)) for k, v in d.items()} for d in days]
    return {"start": str(start), "end": str(end), "days": days, "unanswered": unanswered}


# ---------------- corpus, citation lookup, re-index (FR21, FR20/SR40) ----------------
@router.get("/corpus")
def corpus(cite: str = "", offset: int = 0):
    """100 decisions at a time, the latest ingestion reports, and a citation lookup (the week-1 gate)."""
    lookup = api.STATE["index"].lookup(cite) if cite and api.STATE["index"] else None
    with db.connect() as con:
        decisions = con.execute("""SELECT decision_id, case_name, date_filed, citations, source_url, licence, loaded_at
                                   FROM decisions ORDER BY date_filed DESC LIMIT 100 OFFSET %s""",
                                (max(0, offset),)).fetchall()
        reports = con.execute("SELECT * FROM ingestion_reports ORDER BY id DESC LIMIT 5").fetchall()
    return {"lookup": lookup, "decisions": decisions, "reports": reports, "offset": max(0, offset)}


class Reindex(BaseModel):
    max_words: int = 350


@router.post("/reindex")
def reindex(body: Reindex):
    """Rebuilds chunks and embeddings, reloads the index, then runs the evaluation by itself (SR40)."""
    from app.indexing import build_index
    from app.main import load_index          # imported here: app.main imports this file
    if not 150 <= body.max_words <= 600:
        raise HTTPException(400, "Chunk size must be between 150 and 600 words.")
    db.set_setting("chunk_max_words", body.max_words)

    def work():
        meta = build_index(max_words=body.max_words, log=lambda *a: None)
        load_index()
        run_id = evaluate.run_evaluation(api.STATE["searcher"], api.STATE["index"], "re-index",
                                         f"after re-index ({body.max_words} words)", log=lambda *a: None)
        return f"{meta['chunks']} chunks; regression run {run_id}"
    return {"job": run_in_background("re-index", work)}


# ---------------- accounts (FR12): an administrator creates the other administrators ----------------
@router.get("/users")
def users():
    """Never the password hashes."""
    with db.connect() as con:
        return con.execute("SELECT id, email, role, active, locked_until, created_at FROM users ORDER BY id").fetchall()


# ---------------- the two logs (Yasser, SPEC 11, 2026-11-13) ----------------
# Read by Joe's admin pages (part 2) and by the PDF exports (part 4). ?format=csv downloads the same rows as a
# file; reading a log is itself written to the admin log (app/logs.py, LOGGED_READS).
def log_response(rows, fmt, filename):
    if fmt == "csv":
        return Response(logs.as_csv(rows), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    return logs.as_json(rows)


@router.get("/users/{user_id}/log")
def user_log(user_id: int, format: str = "json"):
    """Everything this account did, newest first."""
    with db.connect() as con:
        if not con.execute("SELECT 1 FROM users WHERE id = %s", (user_id,)).fetchone():
            raise HTTPException(404, "No such account.")
    return log_response(logs.user_log(user_id), format, f"verdicta_user_{user_id}_log.csv")


@router.get("/log")
def admin_log(format: str = "json"):
    """Everything the administrators did, newest first."""
    return log_response(logs.admin_log(), format, "verdicta_admin_log.csv")


class NewUser(BaseModel):
    email: str
    password: str
    role: str = "admin"              # this page makes administrators only; visitors sign up themselves (SPEC 11)


@router.post("/users")
def user_create(body: NewUser):
    if "@" not in body.email or len(body.password) < 10:
        raise HTTPException(400, "Give an email address and a password of at least 10 characters.")
    if body.role != "admin":
        raise HTTPException(400, "This page creates administrators only: visitors make their own account on the sign-up page.")
    db.create_user(body.email, body.password, role=body.role)
    return users()


@router.post("/users/{user_id}/toggle")
def user_toggle(user_id: int, me=Depends(api.require_admin)):
    """Disable or enable an account. You cannot disable yourself (the site would have no admin left)."""
    if user_id == me["id"]:
        raise HTTPException(400, "You cannot disable your own account.")
    with db.connect() as con:
        if not con.execute("UPDATE users SET active = NOT active WHERE id = %s RETURNING id", (user_id,)).fetchone():
            raise HTTPException(404, "No such account.")
    return users()
