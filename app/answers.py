"""Whose answer is it? (Edwin, SPEC 11, 2026-11-20.) An account owns the answers saved with its id; a visitor
without an account owns the answers of its browser session: the session (the signed cookie) remembers the ids of
its last 20 answers. Used to rate an answer, download it as a PDF, or save it; someone else's answer is "not found"."""
from app import db

REMEMBERED = 20


def remember(request, shown):
    """Called for every answer given: a visitor's session keeps its id. Returns the answer unchanged."""
    if not request.session.get("user_id"):
        request.session["my_answers"] = (request.session.get("my_answers", []) + [shown["id"]])[-REMEMBERED:]
    return shown


def owned(request, query_id):
    """The answer (id, question, status, created_at, shown) if it belongs to whoever asks, else None."""
    user_id = request.session.get("user_id")
    with db.connect() as con:
        if user_id:
            return con.execute("SELECT id, question, status, created_at, details->'shown' AS shown FROM query_log "
                               "WHERE id = %s AND user_id = %s", (query_id, user_id)).fetchone()
        if query_id not in request.session.get("my_answers", []):
            return None
        return con.execute("SELECT id, question, status, created_at, details->'shown' AS shown FROM query_log "
                           "WHERE id = %s AND user_id IS NULL", (query_id,)).fetchone()
