"""Email verification codes (Edwin, SPEC 11, 2026-11-20, rule 2).
A 6-digit code, emailed when an account is made with a password. It works for 15 minutes; after 5 wrong tries a new
code is needed; a new code at most once a minute. The table keeps only an HMAC of the code (keyed with the site's
SESSION_SECRET), so a copy of the database does not show the codes."""
import hashlib
import hmac
import secrets
from app import config, db, emails

MINUTES, MAX_TRIES, RESEND_SECONDS = 15, 5, 60


def code_hash(user_id, code):
    return hmac.new(config.SESSION_SECRET.encode(), f"{user_id}:{code}".encode(), hashlib.sha256).hexdigest()


def send_code(user_id, email):
    """Makes a new code, replacing the old one, and emails it. False if the last code was sent less than a
    minute ago (nothing sent)."""
    code = f"{secrets.randbelow(10 ** 6):06d}"
    with db.connect() as con:
        recent = con.execute("SELECT 1 FROM email_codes WHERE user_id = %s "
                             "AND sent_at > now() - make_interval(secs => %s)", (user_id, RESEND_SECONDS)).fetchone()
        if recent:
            return False
        con.execute("""INSERT INTO email_codes (user_id, code_hash, sent_at, expires_at, tries)
                       VALUES (%s, %s, now(), now() + make_interval(mins => %s), 0)
                       ON CONFLICT (user_id) DO UPDATE SET code_hash = EXCLUDED.code_hash, sent_at = now(),
                       expires_at = EXCLUDED.expires_at, tries = 0""", (user_id, code_hash(user_id, code), MINUTES))
    emails.verification_code(email, code, MINUTES)
    return True


def check(user_id, code):
    """"ok" (the account is now verified), "missing", "expired", "tries" (too many wrong tries) or "wrong:N" (N
    tries left). A wrong try is counted before anything else, so guessing is limited to 5 tries per code."""
    with db.connect() as con:
        row = con.execute("SELECT code_hash, tries, expires_at < now() AS expired FROM email_codes "
                          "WHERE user_id = %s", (user_id,)).fetchone()
        if not row:
            return "missing"
        if row["tries"] >= MAX_TRIES:
            return "tries"
        if row["expired"]:
            return "expired"
        if not hmac.compare_digest(row["code_hash"], code_hash(user_id, code.strip())):
            con.execute("UPDATE email_codes SET tries = tries + 1 WHERE user_id = %s", (user_id,))
            left = MAX_TRIES - row["tries"] - 1
            return "tries" if left == 0 else f"wrong:{left}"
        con.execute("DELETE FROM email_codes WHERE user_id = %s", (user_id,))
        con.execute("UPDATE users SET email_verified = TRUE WHERE id = %s", (user_id,))
    return "ok"
