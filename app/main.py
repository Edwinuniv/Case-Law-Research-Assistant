"""The website: the React pages (frontend/dist) and the JSON API (app/api.py, app/api_admin.py).
Visitors use the research page without an account; only administrators log in (step 5.11). The server checks the role on every /api/admin call and every /admin page."""
from contextlib import asynccontextmanager
import traceback
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from app import api, api_admin, api_billing, api_site, config, db, logs
from app.citations import CitationIndex
from app.search import Searcher

STATE = api.STATE                      # shared with the /api routes (app/api.py)


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
if config.HTTPS_ONLY and config.SESSION_SECRET == "change-me-in-production":
    # with the default secret anyone could sign a session cookie and log in as admin
    raise RuntimeError("Set SESSION_SECRET in the environment before running online.")
# the admin log (Yasser, SPEC 11, 2026-11-13): every change through /api/admin and every export is written to it.
# Added BEFORE the session middleware, so it runs inside it and can read who is logged in.
app.middleware("http")(logs.admin_logger)
# session cookie: signed, HttpOnly (JavaScript cannot read it), Secure when HTTPS_ONLY=1, SameSite=Lax
app.add_middleware(SessionMiddleware, secret_key=config.SESSION_SECRET, max_age=8 * 3600,
                   https_only=config.HTTPS_ONLY, same_site="lax")


# Error answers that reveal nothing (Edwin, SPEC 11, 2026-11-19): FastAPI's own 422 answer repeats the values that
# were sent (a password too), and an unexpected error must never show a stack trace, an SQL error or a file path.
# The details go to the server's console only.
@app.exception_handler(RequestValidationError)
async def bad_request(request: Request, exc: RequestValidationError):
    return JSONResponse({"detail": "Some fields are missing or not valid."}, status_code=422)


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    traceback.print_exception(exc)
    return JSONResponse({"detail": "Something went wrong on our side. Please try again."}, status_code=500)


app.include_router(api.router)                                       # JSON API for React (/api/...)
app.include_router(api_admin.router)                                 # admin JSON API (/api/admin/...)
app.include_router(api_site.router)                                  # contact form and site information (Edwin)
app.include_router(api_site.admin)                                   # the contact messages, for the admin
app.include_router(api_billing.router)                                # paid plan, Stripe test mode (Edwin)


@app.get("/health")
def health():
    return {"ok": True, "index_loaded": STATE["searcher"] is not None}


# ======================= REACT FRONT END (step 5.8, at / since step 5.10) =======================
# `npm run build` (in frontend/) writes the app into frontend/dist; the Dockerfile does it on Railway.
# This part comes LAST: FastAPI tries the routes in order, so /api/... and /health are found first.
FRONTEND = config.ROOT / "frontend" / "dist"
if (FRONTEND / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND / "assets"), name="react-assets")


def error_page(status, title, text, link, link_text):
    """A small page in the site's style for the server's own refusals (Edwin, SPEC 11, 2026-11-19): plain words,
    nothing about the account or the server."""
    return HTMLResponse(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{title} · Verdicta</title></head>
<body style="margin:0;min-height:100vh;display:grid;place-items:center;background:#0d0d10;color:#f4f1ea;
font-family:system-ui,sans-serif;text-align:center;padding:16px">
<div><p style="margin:0;font:400 110px/1 Georgia,serif;background:linear-gradient(180deg,#fff,#d4a84a);
-webkit-background-clip:text;background-clip:text;color:transparent">{status}</p>
<h1 style="font:400 28px Georgia,serif;margin:16px 0 8px">{title}</h1>
<p style="color:#b9b4aa;margin:0 0 26px">{text}</p>
<a href="{link}" style="display:inline-block;background:#fff;color:#16171b;border-radius:999px;padding:12px 24px;
font-weight:700;text-decoration:none">{link_text}</a></div></body></html>""", status_code=status)


@app.get("/{path:path}")
def react_app(request: Request, path: str = ""):
    """Every page (/, /login, /admin/...) is the same index.html; React Router then shows the right page.
    The page itself holds no data: every /api call checks the login and the role.
    /admin pages are refused by the server too (401 / 403), as SR35 asks for every admin route."""
    first = path.strip("/").split("/")[0].lower()        # React Router ignores capitals: /ADMIN is admin too
    if first == "api":                                   # an /api address that does not exist: JSON, not a page
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    if first == "admin":
        user_id = request.session.get("user_id")
        if not user_id:
            return error_page(401, "Please log in", "This part of Verdicta is for administrators.", "/login", "Log in")
        if db.active_role(user_id) != "admin":
            return error_page(403, "Administrators only", "This part of Verdicta is for administrators.", "/", "Back to the home page")
    if not (FRONTEND / "index.html").is_file():
        return PlainTextResponse("The React app is not built. Run: cd frontend && npm install && npm run build",
                                 status_code=404)
    return FileResponse(FRONTEND / "index.html")
