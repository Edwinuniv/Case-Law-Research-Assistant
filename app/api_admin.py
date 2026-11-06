"""JSON API for the React admin pages (step 5.9). Same work as the Jinja admin routes in main.py.
EVERY route here is protected by the router itself: CSRF on POST and the admin role checked in the
database at each request (SR35, NFR8). A route cannot be added here without that protection."""
import threading
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app import api, db, evaluate

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
    m = evaluate.metrics(evaluate.load_run(last), s, "test") if last else None
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
    now, then = evaluate.metrics(pairs, s, "test"), evaluate.metrics(pairs, new, "test")
    return {"run": last, "rows": [{"metric": k, "now": now.get(k), "then": then.get(k)} for k in PREVIEW_KEYS]}


class Settings(BaseModel):
    tau_abstain: float
    tau_confident: float
    min_retrieval: float
    top_k: int
    retrieve_k: int
    use_reranker: bool


@router.post("/settings")
def settings_save(body: Settings):
    """The same limits as the Jinja page: tau_confident >= tau_abstain, 8-50 passages searched, 1-10 sent."""
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
    return [{**run, "metrics": evaluate.metrics(evaluate.load_run(run["id"]), s, "test") if run["status"] == "done" else {}}
            for run in runs]


class RunNote(BaseModel):
    note: str = ""


@router.post("/eval/run")
def eval_run(body: RunNote):
    if api.STATE["searcher"] is None:
        raise HTTPException(503, "The search index is not ready yet.")
    job = run_in_background("evaluation", lambda: f"run {evaluate.run_evaluation(api.STATE['searcher'], api.STATE['index'], 'manual', body.note, log=lambda *a: None)}")
    return {"job": job}
