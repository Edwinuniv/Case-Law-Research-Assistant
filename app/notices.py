"""In-app notifications, the bell in the header (Edwin, SPEC 11, 2026-11-20, from CedarPay's notifications).
Written for the same events as the emails (welcome, password changed, plan changed, account disabled or enabled);
at most KEEP per account, the oldest go first."""
from app import db

KEEP = 50


def add(user_id, kind, text, link=None):
    with db.connect() as con:
        con.execute("INSERT INTO notifications (user_id, kind, text, link) VALUES (%s, %s, %s, %s)",
                    (user_id, kind, text, link))
        con.execute("""DELETE FROM notifications WHERE user_id = %s AND id NOT IN
                       (SELECT id FROM notifications WHERE user_id = %s ORDER BY id DESC LIMIT %s)""",
                    (user_id, user_id, KEEP))
