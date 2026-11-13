"""The two logs (Yasser, SPEC section 11, 2026-11-13; part 3 of docs/PLAN_2026-11-13.md).

- The user log: everything an account does (sign-up, logins, logouts, questions, follow-ups, plan changes, refusals).
- The admin log: everything an administrator does (login, logout, every change through /api/admin, the exports).

Every action calls log_user or log_admin. Writing a log never blocks the action: if the database refuses the row,
the error is printed to the server output and the action goes on. No IP address, browser information or password
is ever stored (the privacy page says what is kept). Only administrators read the logs (app/api_admin.py)."""
import csv
import io
import json
import sys

from psycopg.types.json import Jsonb

from app import db

USER_EVENTS = ("signup", "login", "login_failed", "logout", "question", "follow_up", "plan_change", "refused")
# the routes that only READ but are still logged in the admin log: downloading people's data is an action too
LOGGED_READS = ("/export", "/log", "/pdf")


def log_user(user_id, event, detail=None, query_id=None):
    """One row in the user log. event: one of USER_EVENTS. detail: a small dict (never a password or an IP)."""
    if event not in USER_EVENTS:
        raise ValueError(f"unknown user event {event!r}")                # a programming mistake: fail loudly
    try:
        with db.connect() as con:
            con.execute("INSERT INTO user_log (user_id, event, query_id, detail) VALUES (%s, %s, %s, %s)",
                        (user_id, event, query_id, Jsonb(detail or {})))
    except Exception as e:                                               # the log never blocks the action
        print(f"user_log: could not write {event} for user {user_id}: {e}", file=sys.stderr)


def log_admin(admin_id, admin_email, action, target_user_id=None, status=None, detail=None):
    """One row in the admin log. action: a short text such as "login" or "POST /api/admin/settings"."""
    try:
        with db.connect() as con:
            if target_user_id is not None and not con.execute("SELECT 1 FROM users WHERE id = %s",
                                                              (target_user_id,)).fetchone():
                # an action about an account that does not exist (e.g. a 404): keep the row, the id in the detail
                detail, target_user_id = {**(detail or {}), "target_not_found": target_user_id}, None
            con.execute("INSERT INTO admin_log (admin_id, admin_email, action, target_user_id, status, detail) "
                        "VALUES (%s, %s, %s, %s, %s, %s)",
                        (admin_id, admin_email, action, target_user_id, status, Jsonb(detail or {})))
    except Exception as e:
        print(f"admin_log: could not write {action!r} for admin {admin_id}: {e}", file=sys.stderr)


def target_from_path(path):
    """/api/admin/users/7/toggle -> 7: the account an admin action concerns, if the path names one."""
    parts = path.strip("/").split("/")
    if "users" in parts:
        i = parts.index("users")
        if i + 1 < len(parts) and parts[i + 1].isdigit():
            return int(parts[i + 1])
    return None


async def admin_logger(request, call_next):
    """Middleware: every request to /api/admin that changes something (not a GET), and every export, is written to
    the admin log after it ran, with its HTTP status, so a new admin route is logged without extra code."""
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/api/admin") and (request.method != "GET" or any(k in path for k in LOGGED_READS)):
        session = request.scope.get("session") or {}
        admin_id = session.get("user_id")
        if admin_id and db.user_is_active_admin(admin_id):              # refused requests from non-admins: not admin acts
            detail = {"query": str(request.url.query)} if request.url.query else {}
            log_admin(admin_id, session.get("email", ""), f"{request.method} {path}",
                      target_user_id=target_from_path(path), status=response.status_code, detail=detail)
    return response


# ---------------- reading (admins only, through app/api_admin.py) ----------------
def user_log(user_id, limit=500):
    """An account's log, newest first."""
    with db.connect() as con:
        return con.execute("SELECT id, at, event, query_id, detail FROM user_log WHERE user_id = %s "
                           "ORDER BY id DESC LIMIT %s", (user_id, limit)).fetchall()


def admin_log(limit=500, admin_id=None):
    """The admin log, newest first; with admin_id, only that administrator's rows."""
    where, args = ("WHERE admin_id = %s ", (admin_id, limit)) if admin_id is not None else ("", (limit,))
    with db.connect() as con:
        return con.execute("SELECT id, at, admin_email, action, target_user_id, status, detail FROM admin_log "
                           + where + "ORDER BY id DESC LIMIT %s", args).fetchall()


def logs_started():
    """When the first log row was written (the logs began with the 2026-11-13 deploy), or None if both are empty.
    An account created before that has no recorded sign-up or logins: the PDFs say "not recorded", not "never"."""
    with db.connect() as con:
        return con.execute("SELECT LEAST((SELECT min(at) FROM user_log), (SELECT min(at) FROM admin_log)) AS t"
                           ).fetchone()["t"]


def as_json(rows):
    """Rows ready for JSON (dates as ISO text)."""
    return [{k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in r.items()} for r in rows]


def as_csv(rows):
    """Rows as CSV text, one row per line, the detail as JSON; for the download buttons."""
    out = io.StringIO()
    rows = as_json(rows)
    if rows:
        w = csv.DictWriter(out, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow({k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in r.items()})
    return out.getvalue()
