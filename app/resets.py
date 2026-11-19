"""Forgot-password tokens (Edwin, SPEC 11, 2026-11-19).
The emailed token is random (32 bytes); the table keeps only its SHA-256 hash, so a copy of the database gives no
working link. A token works once, for 30 minutes, and only for an active 'user' account."""
import hashlib
import secrets
import bcrypt
from app import db

TOKEN_MINUTES = 30
ONE_EMAIL_PER_SECONDS = 120          # one email per account in 2 minutes: no mail bombing


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def new_token(email):
    """A new token for this email, or None: no account, an administrator, a disabled account, or a link sent
    less than 2 minutes ago. The caller answers the same in every case."""
    with db.connect() as con:
        u = con.execute("SELECT id FROM users WHERE email = %s AND role = 'user' AND active",
                        (email.lower().strip(),)).fetchone()
        if not u:
            return None
        recent = con.execute("SELECT 1 FROM password_resets WHERE user_id = %s "
                             "AND created_at > now() - make_interval(secs => %s)",
                             (u["id"], ONE_EMAIL_PER_SECONDS)).fetchone()
        if recent:
            return None
        token = secrets.token_urlsafe(32)
        con.execute("INSERT INTO password_resets (token_hash, user_id, expires_at) "
                    "VALUES (%s, %s, now() + make_interval(mins => %s))", (token_hash(token), u["id"], TOKEN_MINUTES))
    return token


def use_token(token, password):
    """Sets the new password if the token is valid; returns the account id, or None (wrong, used or expired token,
    or the account is no longer an active 'user'). Deleting the token and reading it is one statement: two clicks
    at the same moment cannot both use it."""
    h = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    with db.connect() as con:
        row = con.execute("""DELETE FROM password_resets r USING users u
                             WHERE r.token_hash = %s AND r.user_id = u.id AND r.expires_at > now()
                               AND u.active AND u.role = 'user'
                             RETURNING r.user_id""", (token_hash(token),)).fetchone()
        if not row:
            return None
        con.execute("UPDATE users SET password_hash = %s, failed_logins = 0, locked_until = NULL WHERE id = %s",
                    (h, row["user_id"]))
        con.execute("DELETE FROM password_resets WHERE user_id = %s", (row["user_id"],))   # every other link too
    return row["user_id"]
