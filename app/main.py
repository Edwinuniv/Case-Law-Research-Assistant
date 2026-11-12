"""The website: the React pages (frontend/dist) and the JSON API (app/api.py, app/api_admin.py).
Visitors use the research page without an account; only administrators log in (step 5.11). The server checks the role on every /api/admin call and every /admin page."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from app import api, api_admin, api_site, config, db
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
# session cookie: signed, HttpOnly (JavaScript cannot read it), Secure when HTTPS_ONLY=1, SameSite=Lax
app.add_middleware(SessionMiddleware, secret_key=config.SESSION_SECRET, max_age=8 * 3600,
                   https_only=config.HTTPS_ONLY, same_site="lax")
app.include_router(api.router)                                       # JSON API for React (/api/...)
app.include_router(api_admin.router)                                 # admin JSON API (/api/admin/...)
app.include_router(api_site.router)                                  # contact form and site information (Edwin)
app.include_router(api_site.admin)                                   # the contact messages, for the admin


@app.get("/health")
def health():
    return {"ok": True, "index_loaded": STATE["searcher"] is not None}


# ======================= REACT FRONT END (step 5.8, at / since step 5.10) =======================
# `npm run build` (in frontend/) writes the app into frontend/dist; the Dockerfile does it on Railway.
# This part comes LAST: FastAPI tries the routes in order, so /api/... and /health are found first.
FRONTEND = config.ROOT / "frontend" / "dist"
if (FRONTEND / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND / "assets"), name="react-assets")


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
            return HTMLResponse('401 - please <a href="/login">log in</a> as an administrator.', status_code=401)
        if db.active_role(user_id) != "admin":
            return PlainTextResponse("403 - administrators only", status_code=403)
    if not (FRONTEND / "index.html").is_file():
        return PlainTextResponse("The React app is not built. Run: cd frontend && npm install && npm run build",
                                 status_code=404)
    return FileResponse(FRONTEND / "index.html")
