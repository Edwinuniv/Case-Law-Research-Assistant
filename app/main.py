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
