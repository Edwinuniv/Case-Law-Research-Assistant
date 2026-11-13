"""PDF exports for the administrators (Yasser, SPEC section 11, 2026-11-13; part 4 of docs/PLAN_2026-11-13.md).

- user_pdf(user_id): one account: its details, its log (from the user log) and its questions (from query_log).
- users_pdf(): the list of all accounts with the same details, one row each.

The figures are counted at the moment of the export from the logs (app/logs.py) and query_log, so they are always
up to date. Made with ReportLab (BSD licence); nothing is sent anywhere. No IP or password: the logs have none."""
import datetime
import io
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app import db, logs

SEAL = Path(__file__).parent / "assets" / "seal.png"
INK, GOLD, LINE, SOFT = colors.HexColor("#1c1917"), colors.HexColor("#b45309"), colors.HexColor("#d6d3d1"), colors.HexColor("#f5f5f4")
TITLE = ParagraphStyle("t", fontName="Times-Bold", fontSize=20, leading=24, textColor=INK)
H2 = ParagraphStyle("h", fontName="Times-Bold", fontSize=13, leading=16, textColor=GOLD, spaceBefore=12, spaceAfter=6)
SMALL = ParagraphStyle("s", fontName="Helvetica", fontSize=8.5, leading=11, textColor=colors.HexColor("#57534e"))
CELL = ParagraphStyle("c", fontName="Helvetica", fontSize=8.5, leading=10.5, textColor=INK)
HEAD = ParagraphStyle("hc", fontName="Helvetica-Bold", fontSize=8.5, leading=10.5, textColor=colors.white)

# the details of each account, counted from the logs: logins and last activity come from the user log for a
# visitor's account and from the admin log for an administrator
SUMMARY = """
SELECT u.*, COALESCE(ul.logins, al.logins, 0) AS logins, COALESCE(ul.last_login, al.last_login) AS last_login,
       GREATEST(ul.last_act, al.last_act) AS last_activity,
       (SELECT count(*) FROM query_log q WHERE q.user_id = u.id) AS questions
FROM users u
LEFT JOIN (SELECT user_id, count(*) FILTER (WHERE event = 'login') AS logins,
                  max(at) FILTER (WHERE event = 'login') AS last_login, max(at) AS last_act
           FROM user_log GROUP BY user_id) ul ON ul.user_id = u.id
LEFT JOIN (SELECT admin_id, count(*) FILTER (WHERE action = 'login') AS logins,
                  max(at) FILTER (WHERE action = 'login') AS last_login, max(at) AS last_act
           FROM admin_log GROUP BY admin_id) al ON al.admin_id = u.id
"""
HIDDEN = ("password_hash", "failed_logins", "locked_until")               # never in a PDF


def summaries(user_id=None):
    """Every account's details (or one account's), without the password hash."""
    with db.connect() as con:
        if user_id is None:
            rows = con.execute(SUMMARY + " ORDER BY u.id").fetchall()
        else:
            rows = con.execute(SUMMARY + " WHERE u.id = %s", (user_id,)).fetchall()
    return [{k: v for k, v in r.items() if k not in HIDDEN} for r in rows]


def when(v):
    """A date in UTC, like the PDF's header (the database may give local time)."""
    if isinstance(v, datetime.datetime):
        return v.astimezone(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M")
    return "" if v is None else str(v)


def p(text, style=CELL):
    return Paragraph(escape("" if text is None else str(text)), style)


def before_logs(u, started):
    """True if the account existed before the logs began, so 'no login' only means 'not recorded'."""
    return started is None or (u["created_at"] is not None and u["created_at"] < started)


def last_login_text(u, started):
    return when(u["last_login"]) or ("not recorded" if before_logs(u, started) else "never")


def detail_text(d):
    """{'reason': 'wrong password'} -> 'reason: wrong password'"""
    return "; ".join(f"{k}: {v}" for k, v in (d or {}).items())


def table(head, rows, widths):
    t = Table([[p(h, HEAD) for h in head]] + [[c if isinstance(c, Paragraph) else p(c) for c in r] for r in rows],
              colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), INK), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SOFT]),
                           ("LINEBELOW", (0, 0), (-1, -1), 0.25, LINE), ("TOPPADDING", (0, 0), (-1, -1), 4),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    return t


def header(title, admin_email, width):
    made = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    logo = Image(str(SEAL), width=1.6 * cm, height=1.6 * cm)
    t = Table([[logo, [p(title, TITLE), p(f"Verdicta · made {made} by {admin_email} · administrators only · "
                                         f"times in UTC", SMALL)]]], colWidths=[2 * cm, width - 2 * cm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, 0), 1, GOLD),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    return [t, Spacer(1, 10)]


def build(story, pagesize):
    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=pagesize, leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                            topMargin=1.4 * cm, bottomMargin=1.4 * cm, title="Verdicta export", author="Verdicta")

    def page_number(canvas, d):
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#78716c"))
        canvas.drawRightString(pagesize[0] - 1.5 * cm, 0.8 * cm, f"Page {d.page}")
    doc.build(story, onFirstPage=page_number, onLaterPages=page_number)
    return out.getvalue()


def user_pdf(user_id, admin_email):
    """One account: details, log, questions. None if the account does not exist."""
    found = summaries(user_id)
    if not found:
        return None
    u, width, started = found[0], A4[0] - 3 * cm, logs.logs_started()
    details = [["Email", u["email"]], ["Role", u["role"]], ["Plan", u.get("plan") or "—"],
               ["Active", "yes" if u["active"] else "no (disabled)"], ["Signed up", when(u["created_at"])],
               ["Last login", last_login_text(u, started)],
               ["Number of logins", f"{u['logins']} since the logs began" if before_logs(u, started) else u["logins"]],
               ["Last activity", when(u["last_activity"]) or "—"], ["Questions asked", u["questions"]]]
    d = Table([[p(k, HEAD), p(v)] for k, v in details], colWidths=[4.2 * cm, width - 4.2 * cm])
    d.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), INK), ("LINEBELOW", (0, 0), (-1, -1), 0.25, LINE),
                           ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    story = header(f"Account: {u['email']}", admin_email, width) + [p("Details", H2), d]

    if u["role"] == "admin":                                         # an administrator's actions are in the admin log
        # a failed login on an admin's email is an attempt ON the account (by anyone), not an action by the admin
        rows = [[when(r["at"]), "failed login attempt on this account" if r["action"] == "login_failed" else r["action"],
                 r["status"] or "", detail_text(r["detail"])] for r in logs.admin_log(limit=5000, admin_id=user_id)]
        story += [p(f"Admin log ({len(rows)} rows, newest first)", H2),
                  table(["When", "Action", "Status", "Detail"], rows or [["", "nothing yet", "", ""]],
                        [3 * cm, 7.5 * cm, 1.5 * cm, width - 12 * cm])]
    else:
        rows = [[when(r["at"]), r["event"], r["query_id"] or "", detail_text(r["detail"])] for r in logs.user_log(user_id, 2000)]
        story += [p(f"Log ({len(rows)} rows, newest first)", H2),
                  table(["When", "Event", "Question id", "Detail"], rows or [["", "nothing yet", "", ""]],
                        [3 * cm, 2.8 * cm, 2.2 * cm, width - 8 * cm])]
    with db.connect() as con:
        qs = con.execute("SELECT id, created_at, status, question FROM query_log WHERE user_id = %s ORDER BY id DESC",
                         (user_id,)).fetchall()
    story += [p(f"Questions ({len(qs)}, newest first)", H2),
              table(["Id", "When", "Status", "Question"], [[q["id"], when(q["created_at"]), q["status"], q["question"]]
                                                           for q in qs] or [["", "", "", "no question yet"]],
                    [1.4 * cm, 3 * cm, 3.2 * cm, width - 7.6 * cm])]
    return build(story, A4)


def users_pdf(admin_email):
    """The list of all accounts, one row each, on landscape pages."""
    us, width, started = summaries(), landscape(A4)[0] - 3 * cm, logs.logs_started()
    rows = [[u["id"], u["email"], u["role"], u.get("plan") or "—", "yes" if u["active"] else "no", when(u["created_at"]),
             last_login_text(u, started), u["logins"], when(u["last_activity"]) or "—", u["questions"]] for u in us]
    note = (f"Logs kept since {when(started)} UTC: logins before that are not recorded." if started
            else "No log row yet: logins are not recorded.")
    story = header(f"All accounts ({len(us)})", admin_email, width) + [p(note, SMALL), Spacer(1, 6),
        table(["Id", "Email", "Role", "Plan", "Active", "Signed up", "Last login", "Logins", "Last activity", "Questions"],
              rows or [["", "no account", "", "", "", "", "", "", "", ""]],
              [1.1 * cm, 6.0 * cm, 1.6 * cm, 1.6 * cm, 1.4 * cm, 3 * cm, 3 * cm, 1.5 * cm, 3 * cm, 2.2 * cm])]
    return build(story, landscape(A4))
