"""JSON API for the React admin pages (step 5.9). Same work as the Jinja admin routes in main.py.
EVERY route here is protected by the router itself: CSRF on POST and the admin role checked in the
database at each request (SR35, NFR8). A route cannot be added here without that protection."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app import api, db, evaluate

router = APIRouter(prefix="/api/admin",
                   dependencies=[Depends(api.check_csrf), Depends(api.require_admin)])


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
