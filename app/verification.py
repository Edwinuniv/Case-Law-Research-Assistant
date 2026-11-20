"""Email verification codes (Edwin, SPEC 11, 2026-11-20, rule 2).
A 6-digit code, emailed when an account is made with a password. It works for 15 minutes; after 5 wrong tries a new
code is needed; a new code at most once a minute, and at most 5 codes per account in 24 hours, the sign-up's included
(Yasser's review: otherwise 5 tries x a code a minute = 7,200 guesses a day; now at most 25). The table keeps only an HMAC of the code (keyed with the site's
SESSION_SECRET), so a copy of the database does not show the codes."""
import hashlib
import hmac
import secrets
from app import config, db, emails

MINUTES, MAX_TRIES, RESEND_SECONDS = 15, 5, 60
CODES_PER_DAY = 5


def code_hash(user_id, code):
    return hmac.new(config.SESSION_SECRET.encode(), f"{user_id}:{code}".encode(), hashlib.sha256).hexdigest()


def send_code(user_id, email):
    """Makes a new code, replacing the old one, and emails it: "sent". Nothing is sent if the last code is less than
    a minute old ("wait") or if 5 codes were already sent in the last 24 hours ("daily")."""
    code = f"{secrets.randbelow(10 ** 6):06d}"
    with db.connect() as con:
        # FOR UPDATE: two requests at the same moment wait for each other, so both cannot pass the checks below
        row = con.execute("""SELECT sent_at > now() - make_interval(secs => %s) AS recent,
                                    window_start > now() - interval '24 hours' AS same_day, sent_in_window
                             FROM email_codes WHERE user_id = %s FOR UPDATE""", (RESEND_SECONDS, user_id)).fetchone()
        if row and row["recent"]:
            return "wait"
        if row and row["same_day"] and row["sent_in_window"] >= CODES_PER_DAY:
            return "daily"
        same_day = bool(row and row["same_day"])
        con.execute("""INSERT INTO email_codes (user_id, code_hash, sent_at, expires_at, tries, window_start, sent_in_window)
                       VALUES (%s, %s, now(), now() + make_interval(mins => %s), 0, now(), 1)
                       ON CONFLICT (user_id) DO UPDATE SET code_hash = EXCLUDED.code_hash, sent_at = now(),
                       expires_at = EXCLUDED.expires_at, tries = 0,
                       window_start = CASE WHEN %s THEN email_codes.window_start ELSE now() END,
                       sent_in_window = CASE WHEN %s THEN email_codes.sent_in_window + 1 ELSE 1 END""",
                    (user_id, code_hash(user_id, code), MINUTES, same_day, same_day))
    emails.verification_code(email, code, MINUTES)
    return "sent"


def check(user_id, code):
    """"ok" (the account is now verified), "missing", "expired", "tries" (too many wrong tries) or "wrong:N" (N
    tries left). The try is counted FIRST, in the same statement that checks it is allowed (Yasser's review): guesses
    sent at the same moment cannot all read "0 tries", so a code gets 5 comparisons at most."""
    with db.connect() as con:
        row = con.execute("""UPDATE email_codes SET tries = tries + 1
                             WHERE user_id = %s AND tries < %s AND expires_at > now()
                             RETURNING code_hash, tries""", (user_id, MAX_TRIES)).fetchone()
        if not row:                                   # no try left to count: say why
            why = con.execute("SELECT tries >= %s AS used, expires_at <= now() AS expired FROM email_codes "
                              "WHERE user_id = %s", (MAX_TRIES, user_id)).fetchone()
            return "missing" if not why else "tries" if why["used"] else "expired"
        if not hmac.compare_digest(row["code_hash"], code_hash(user_id, code.strip())):
            left = MAX_TRIES - row["tries"]
            return "tries" if left == 0 else f"wrong:{left}"
        con.execute("DELETE FROM email_codes WHERE user_id = %s", (user_id,))
        con.execute("UPDATE users SET email_verified = TRUE WHERE id = %s", (user_id,))
    return "ok"
