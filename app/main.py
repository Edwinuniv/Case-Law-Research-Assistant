"""The website. Public part: research page (no login, SR33). Admin part: /admin/* (login + role)."""
import datetime
import re
import threading
from urllib.parse import quote
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from app import config, db, evaluate
from app.citations import CitationIndex
from app.indexing import build_index
from app.pipeline import answer, check_input
from app.search import Searcher

templates = Jinja2Templates(directory=str(config.ROOT / "app" / "templates"))
STATE = {"searcher": None, "index": None}


def load_index():
    """(Re)load the search index and citation index from PostgreSQL."""
    with db.connect() as con:
        n = con.execute("SELECT count(*) AS n FROM chunks").fetchone()["n"]
    if n == 0:
        print("The chunks table is empty. Run: python -m scripts.seed --index")
        return
    STATE["searcher"], STATE["index"] = Searcher(), CitationIndex()


@asynccontextmanager
async def lifespan(app):
    db.init_db()
    load_index()
    yield


app = FastAPI(title="Verdicta", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=config.SESSION_SECRET, max_age=8 * 3600,
                   https_only=config.HTTPS_ONLY)


def page(request, name, status_code=200, **context):
    return templates.TemplateResponse(request, name, {"admin": request.session.get("admin"),
                                                      "config": config, **context},
                                      status_code=status_code)


def decision_info(decision_ids):
    with db.connect() as con:
        rows = con.execute("SELECT decision_id, citations, docket_number, source_url FROM decisions "
                           "WHERE decision_id = ANY(%s)", (list(decision_ids),)).fetchall()
    return {r["decision_id"]: r for r in rows}


# ======================= PUBLIC PART =======================
@app.get("/")
def home(request: Request):
    return page(request, "ask.html", result=None, question="", error=None)


@app.post("/ask")
def ask(request: Request, question: str = Form("")):
    error = check_input(question)                                    # SR3
    if error or STATE["searcher"] is None:
        return page(request, "ask.html", result=None, question=question,
                    error=error or "The search index is not ready yet.")
    result = answer(question, STATE["searcher"], STATE["index"], db.get_settings())
    db.log_query(result)                                             # FR28, SR41
    info = decision_info({p["decision_id"] for _, p in result["passages"]})
    return page(request, "ask.html", result=result, question=question, error=None, info=info)


@app.get("/passage/{chunk_id}")
def passage(request: Request, chunk_id: str, quote: str = "", panel: int = 0):
    with db.connect() as con:
        c = con.execute("""SELECT c.*, o.text AS opinion_text, o.label, d.case_name, d.date_filed,
                           d.citations, d.docket_number, d.source_url, d.licence
                           FROM chunks c JOIN opinions o USING (opinion_id)
                           JOIN decisions d ON d.decision_id = c.decision_id
                           WHERE c.chunk_id = %s""", (chunk_id,)).fetchone()
    if not c:
        return HTMLResponse("Passage not found", status_code=404)
    text = c["opinion_text"]
    inside = text[c["start_char"]:c["end_char"]]
    # find the quote even if spaces, line breaks or capitals differ
    pattern = r"\s+".join(re.escape(w) for w in quote.split())
    m = re.search(pattern, inside, re.IGNORECASE) if pattern else None
    return page(request, "passage_panel.html" if panel else "passage.html", c=c,
                before=text[max(0, c["start_char"] - 2500):c["start_char"]],
                inside_before=inside[:m.start()] if m else inside, marked=inside[m.start():m.end()] if m else "",
                inside_after=inside[m.end():] if m else "", after=text[c["end_char"]:c["end_char"] + 2500])


@app.get("/health")
def health():
    return {"ok": True, "index_loaded": STATE["searcher"] is not None}


# ======================= ADMIN: login and role check =======================
def need_admin(request):
    """NFR8 / SR35: checked on EVERY admin request. Returns an error response, or None if allowed."""
    admin = request.session.get("admin")
    if not admin:
        return page(request, "admin/login.html", status_code=401, error="Please log in as an administrator.")
    if not db.user_is_active_admin(admin["id"]):
        request.session.clear()
        return HTMLResponse("403 - this account is disabled or not an administrator", status_code=403)
    return None


@app.get("/admin/login")
def login_form(request: Request):
    return page(request, "admin/login.html", error=None)


@app.post("/admin/login")
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    user, message = db.check_login(email, password)
    if not user:
        return page(request, "admin/login.html", status_code=401, error=message)
    request.session["admin"] = user
    return RedirectResponse("/admin", 303)


@app.get("/admin/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", 303)


def run_in_background(kind, work):
    job_id = db.start_job(kind)

    def target():
        try:
            db.end_job(job_id, "done", str(work() or ""))
        except Exception as e:
            db.end_job(job_id, "failed", f"{type(e).__name__}: {e}")
    threading.Thread(target=target, daemon=True).start()


# ======================= ADMIN: overview and settings =======================
@app.get("/admin")
def admin_home(request: Request):
    if (r := need_admin(request)):
        return r
    s = db.get_settings()
    with db.connect() as con:
        counts = con.execute("""SELECT (SELECT count(*) FROM decisions) AS decisions,
            (SELECT count(*) FROM opinions) AS opinions, (SELECT count(*) FROM chunks) AS chunks,
            (SELECT count(*) FROM citations) AS citations, (SELECT count(*) FROM citation_map) AS citation_map,
            (SELECT count(*) FROM test_questions) AS questions,
            (SELECT count(*) FROM query_log WHERE created_at::date = now()::date) AS queries_today""").fetchone()
        last = con.execute("SELECT id FROM eval_runs WHERE status = 'done' ORDER BY id DESC LIMIT 1").fetchone()
        jobs = con.execute("SELECT * FROM jobs ORDER BY id DESC LIMIT 6").fetchall()
    m = evaluate.metrics(evaluate.load_run(last["id"]), s, "test") if last else None
    return page(request, "admin/home.html", counts=counts, s=s, last=last, m=m, jobs=jobs)


@app.get("/admin/settings")
def admin_settings(request: Request, tau_abstain: float = None, tau_confident: float = None,
                   min_retrieval: float = None):
    """FR23: preview the effect of new thresholds on the latest evaluation run BEFORE saving."""
    if (r := need_admin(request)):
        return r
    s = db.get_settings()
    preview = None
    with db.connect() as con:
        last = con.execute("SELECT id FROM eval_runs WHERE status = 'done' ORDER BY id DESC LIMIT 1").fetchone()
    if last and tau_abstain is not None:
        new = dict(s, tau_abstain=tau_abstain, tau_confident=max(tau_confident or 0, tau_abstain),
                   min_retrieval=min_retrieval if min_retrieval is not None else s["min_retrieval"])
        pairs = evaluate.load_run(last["id"])
        preview = {"run": last["id"], "new": new, "now": evaluate.metrics(pairs, s, "test"),
                   "then": evaluate.metrics(pairs, new, "test")}
    return page(request, "admin/settings.html", s=s, preview=preview)


@app.post("/admin/settings")
def admin_settings_save(request: Request, tau_abstain: float = Form(...), tau_confident: float = Form(...),
                        min_retrieval: float = Form(...), top_k: int = Form(...), retrieve_k: int = Form(...),
                        use_reranker: str = Form("off")):
    if (r := need_admin(request)):
        return r
    db.set_setting("tau_abstain", tau_abstain)
    db.set_setting("tau_confident", max(tau_confident, tau_abstain))
    db.set_setting("min_retrieval", min_retrieval)
    db.set_setting("retrieve_k", max(8, min(retrieve_k, 50)))
    db.set_setting("top_k", max(1, min(top_k, 10)))
    db.set_setting("use_reranker", use_reranker == "on")
    return RedirectResponse("/admin/settings", 303)


# ======================= ADMIN: evaluation =======================
@app.get("/admin/eval")
def admin_eval(request: Request):
    if (r := need_admin(request)):
        return r
    s = db.get_settings()
    with db.connect() as con:
        runs = con.execute("SELECT * FROM eval_runs ORDER BY id DESC").fetchall()
    rows = [(run, evaluate.metrics(evaluate.load_run(run["id"]), s, "test") if run["status"] == "done" else {})
            for run in runs]
    return page(request, "admin/eval.html", rows=rows, s=s)


@app.post("/admin/eval/run")
def admin_eval_run(request: Request, note: str = Form("")):
    if (r := need_admin(request)):
        return r
    run_in_background("evaluation", lambda: f"run {evaluate.run_evaluation(STATE['searcher'], STATE['index'], 'manual', note, log=lambda *a: None)}")
    return RedirectResponse("/admin/eval", 303)


@app.get("/admin/eval/compare")
def admin_eval_compare(request: Request, a: int, b: int, split: str = "test"):
    if (r := need_admin(request)):
        return r
    rows, flips = evaluate.compare(a, b, db.get_settings(), split or None)
    return page(request, "admin/compare.html", a=a, b=b, rows=rows, flips=flips, split=split)


@app.get("/admin/eval/{run_id}")
def admin_eval_detail(request: Request, run_id: int, split: str = "test", tau: float = None):
    if (r := need_admin(request)):
        return r
    s = db.get_settings()
    if tau is not None:
        s = dict(s, tau_abstain=tau, tau_confident=max(tau, s["tau_confident"]))
    pairs = evaluate.load_run(run_id)
    table = []
    for q, res in pairs:
        st = evaluate.status_at(res, s)
        ok = (st == "NOT_SUPPORTED") == (q["tag"] != "answerable")
        table.append({"q": q, "r": res, "status": st, "ok": ok,
                      "false": sum(len(x) for x in res["false_by_sentence"]) if st in ("ANSWERED", "LOW_CONFIDENCE") else 0})
    table.sort(key=lambda t: (t["ok"], t["q"]["id"]))
    return page(request, "admin/eval_run.html", run_id=run_id, split=split, s=s, table=table,
                m=evaluate.metrics(pairs, s, split or None), sweep=evaluate.sweep(pairs, s, "tune"))


# ======================= ADMIN: test questions (FR13a-c) =======================
@app.get("/admin/questions")
def admin_questions(request: Request, tag: str = ""):
    if (r := need_admin(request)):
        return r
    qs = [q for q in evaluate.load_questions() if not tag or q["tag"] == tag]
    return page(request, "admin/questions.html", questions=qs, tag=tag)


@app.get("/admin/questions/export")
def admin_questions_export(request: Request):
    if (r := need_admin(request)):
        return r
    return PlainTextResponse(evaluate.export_questions(), media_type="application/x-ndjson",
                             headers={"Content-Disposition": "attachment; filename=questions.jsonl"})


@app.get("/admin/questions/edit")
def admin_question_form(request: Request, id: str = "", question: str = "", tag: str = "answerable"):
    if (r := need_admin(request)):
        return r
    q = next((x for x in evaluate.load_questions() if x["id"] == id), None) if id else None
    return page(request, "admin/question_form.html", q=q, prefill_question=question, prefill_tag=tag)


@app.post("/admin/questions/save")
def admin_question_save(request: Request, id: str = Form(...), tag: str = Form(...), split: str = Form(...),
                        question: str = Form(...), expected_answer: str = Form(""), gold_decision_ids: str = Form(""),
                        gold_quote: str = Form(""), must_not_appear: str = Form(""), why: str = Form(""),
                        author: str = Form("")):
    if (r := need_admin(request)):
        return r
    ids = [int(x) for x in gold_decision_ids.replace(",", " ").split() if x.isdigit()]
    forbidden = [x.strip() for x in must_not_appear.split(";") if x.strip()]
    with db.connect() as con:
        con.execute("""INSERT INTO test_questions (id, tag, split, question, expected_answer, gold_decision_ids,
            gold_quote, must_not_appear, why, author, updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())
            ON CONFLICT (id) DO UPDATE SET tag = EXCLUDED.tag, split = EXCLUDED.split, question = EXCLUDED.question,
            expected_answer = EXCLUDED.expected_answer, gold_decision_ids = EXCLUDED.gold_decision_ids,
            gold_quote = EXCLUDED.gold_quote, must_not_appear = EXCLUDED.must_not_appear, why = EXCLUDED.why,
            author = EXCLUDED.author, updated_at = now()""",
                    (id.strip(), tag, split, question, expected_answer, ids, gold_quote, forbidden, why, author))
    return RedirectResponse("/admin/questions", 303)


# ======================= ADMIN: abstentions / failures (FR22, SR43) =======================
@app.get("/admin/abstentions")
def admin_abstentions(request: Request, status: str = "NOT_SUPPORTED"):
    if (r := need_admin(request)):
        return r
    with db.connect() as con:
        rows = con.execute("SELECT * FROM query_log WHERE status = %s ORDER BY id DESC LIMIT 200", (status,)).fetchall()
        ids = [cid for row in rows for _, cid, _ in (row["details"] or {}).get("passages", [])]
        chunks = {c["chunk_id"]: c for c in con.execute(
            "SELECT c.chunk_id, d.case_name, o.label FROM chunks c JOIN opinions o USING (opinion_id) "
            "JOIN decisions d ON d.decision_id = c.decision_id WHERE c.chunk_id = ANY(%s)", (ids,)).fetchall()}
    return page(request, "admin/abstentions.html", rows=rows, chunks=chunks, status=status)


@app.post("/admin/abstentions/{log_id}/label")
def admin_label(request: Request, log_id: int, label: str = Form(...)):
    if (r := need_admin(request)):
        return r
    with db.connect() as con:
        q = con.execute("UPDATE query_log SET label = %s WHERE id = %s RETURNING question", (label, log_id)).fetchone()
    if label.startswith("add as"):                                  # SR43: add it to the test set
        tag = "unanswerable" if "unanswerable" in label else "answerable"
        return RedirectResponse(f"/admin/questions/edit?question={quote(q['question'])}&tag={tag}", 303)
    return RedirectResponse("/admin/abstentions", 303)


# ======================= ADMIN: analytics (FR24-27, SR42) =======================
@app.get("/admin/analytics")
def admin_analytics(request: Request, start: str = "", end: str = ""):
    if (r := need_admin(request)):
        return r
    today = datetime.date.today()
    start = start or str(today - datetime.timedelta(days=30))
    end = end or str(today)
    with db.connect() as con:
        days = con.execute("""SELECT created_at::date AS day, count(*) AS n,
              percentile_cont(0.5) WITHIN GROUP (ORDER BY ms_total) AS p50,
              percentile_cont(0.95) WITHIN GROUP (ORDER BY ms_total) AS p95,
              avg((status = 'ERROR')::int) AS failure_rate,
              sum((status = 'ANSWERED')::int) AS answered, sum((status = 'LOW_CONFIDENCE')::int) AS low,
              sum((status = 'NOT_SUPPORTED')::int) AS not_supported, sum((status = 'ERROR')::int) AS errors
              FROM query_log WHERE created_at::date BETWEEN %s AND %s GROUP BY 1 ORDER BY 1""",
                           (start, end)).fetchall()
        days = [{k: (str(v) if k == "day" else float(v or 0)) for k, v in d.items()} for d in days]
        unanswered = con.execute("""SELECT created_at, question, reason FROM query_log
              WHERE status = 'NOT_SUPPORTED' AND created_at::date BETWEEN %s AND %s
              ORDER BY id DESC LIMIT 50""", (start, end)).fetchall()
    return page(request, "admin/analytics.html", days=days, unanswered=unanswered, start=start, end=end)


# ======================= ADMIN: corpus, citation lookup, re-index =======================
@app.get("/admin/corpus")
def admin_corpus(request: Request, cite: str = "", offset: int = 0):
    if (r := need_admin(request)):
        return r
    lookup = STATE["index"].lookup(cite) if cite and STATE["index"] else None
    with db.connect() as con:
        decisions = con.execute("SELECT * FROM decisions ORDER BY date_filed DESC LIMIT 100 OFFSET %s",
                                (offset,)).fetchall()
        reports = con.execute("SELECT * FROM ingestion_reports ORDER BY id DESC LIMIT 5").fetchall()
    return page(request, "admin/corpus.html", decisions=decisions, reports=reports, cite=cite,
                lookup=lookup, offset=offset)


@app.post("/admin/reindex")
def admin_reindex(request: Request, max_words: int = Form(350)):
    """FR21 + FR20/SR40: rebuild the index, then run the evaluation automatically."""
    if (r := need_admin(request)):
        return r
    db.set_setting("chunk_max_words", max_words)

    def work():
        meta = build_index(max_words=max_words, log=lambda *a: None)
        load_index()
        run_id = evaluate.run_evaluation(STATE["searcher"], STATE["index"], "re-index",
                                         f"after re-index ({max_words} words)", log=lambda *a: None)
        return f"{meta['chunks']} chunks; regression run {run_id}"
    run_in_background("re-index", work)
    return RedirectResponse("/admin", 303)


# ======================= ADMIN: accounts (FR12) =======================
@app.get("/admin/users")
def admin_users(request: Request):
    if (r := need_admin(request)):
        return r
    with db.connect() as con:
        users = con.execute("SELECT id, email, role, active, locked_until, created_at FROM users ORDER BY id").fetchall()
    return page(request, "admin/users.html", users=users)


@app.post("/admin/users")
def admin_user_create(request: Request, email: str = Form(...), password: str = Form(...)):
    if (r := need_admin(request)):
        return r
    if len(password) >= 10:
        db.create_user(email, password)
    return RedirectResponse("/admin/users", 303)


@app.post("/admin/users/{user_id}/toggle")
def admin_user_toggle(request: Request, user_id: int):
    if (r := need_admin(request)):
        return r
    if user_id != request.session["admin"]["id"]:                  # you cannot disable yourself
        with db.connect() as con:
            con.execute("UPDATE users SET active = NOT active WHERE id = %s", (user_id,))
    return RedirectResponse("/admin/users", 303)
