"""Login and roles in the database (SR33, SR34, SR36; step 5.6, roles back to SR33 as written in 5.11).
Uses the TEST database."""
import pytest

PW = "a-long-password"


def test_every_login_failure_gives_the_same_message(clean_db):
    clean_db.create_user("boss@example.com", PW)
    clean_db.create_user("gone@example.com", PW)
    with clean_db.connect() as con:
        con.execute("UPDATE users SET active = FALSE WHERE email = 'gone@example.com'")
    unknown = clean_db.check_login("nobody@example.com", PW)
    wrong = clean_db.check_login("boss@example.com", "wrong")
    disabled = clean_db.check_login("gone@example.com", PW)
    for _ in range(5):
        clean_db.check_login("boss@example.com", "wrong")
    locked = clean_db.check_login("boss@example.com", PW)
    assert unknown == wrong == disabled == locked == (None, "Wrong email or password.")


def test_lock_lasts_fifteen_minutes(clean_db):                                      # SR36
    clean_db.create_user("boss@example.com", PW)
    for _ in range(5):
        clean_db.check_login("boss@example.com", "wrong")
    with clean_db.connect() as con:
        minutes = con.execute("SELECT extract(epoch FROM locked_until - now()) / 60 AS m FROM users").fetchone()["m"]
        assert 14 < minutes <= 15
        con.execute("UPDATE users SET locked_until = now() - interval '1 second'")   # 15 minutes later
    user, _ = clean_db.check_login("boss@example.com", PW)
    assert user["email"] == "boss@example.com"


def test_four_failures_do_not_lock(clean_db):
    clean_db.create_user("boss@example.com", PW)
    for _ in range(4):
        clean_db.check_login("boss@example.com", "wrong")
    user, _ = clean_db.check_login("boss@example.com", PW)
    assert user is not None


def test_the_roles_are_admin_and_user(clean_db):                                  # SPEC 11 (2026-11-12)
    """Since the visitor-accounts decision: 'admin' (seed, Accounts page) and 'user' (sign-up). An account is an
    administrator by default; a 'user' is never an administrator; any other role is refused, by the database too."""
    clean_db.create_user("boss@example.com", PW)                     # admin by default (seed.py)
    boss, _ = clean_db.check_login("boss@example.com", PW)
    assert boss["role"] == "admin" and clean_db.user_is_active_admin(boss["id"])
    reader_id = clean_db.create_visitor("reader@example.com", PW)
    assert clean_db.active_role(reader_id) == "user" and not clean_db.user_is_active_admin(reader_id)
    with clean_db.connect() as con:                                  # the database refuses another role
        with pytest.raises(Exception):
            con.execute("INSERT INTO users (email, password_hash, role) VALUES ('r@example.com', 'x', 'superuser')")


def test_unknown_role_is_refused(clean_db):
    with pytest.raises(ValueError):
        clean_db.create_user("x@example.com", PW, role="superuser")
    with clean_db.connect() as con:
        assert con.execute("SELECT count(*) AS n FROM users").fetchone()["n"] == 0


def test_disabled_account_has_no_role(clean_db):
    clean_db.create_user("boss@example.com", PW)
    with clean_db.connect() as con:
        con.execute("UPDATE users SET active = FALSE")
        uid = con.execute("SELECT id FROM users").fetchone()["id"]
    assert clean_db.active_role(uid) is None
    assert clean_db.active_role(99999) is None                       # no such account


def test_existing_database_keeps_its_accounts_and_questions(clean_db):          # SPEC 11 (2026-11-12)
    """Until 2026-11-12 the start-up migration deleted every 'user' account (step 5.11). Now init_db keeps them,
    with their questions, and an old database whose rule allowed 'admin' only accepts 'user' afterwards."""
    clean_db.create_user("boss@example.com", PW)
    uid = clean_db.create_visitor("reader@example.com", PW)
    with clean_db.connect() as con:
        con.execute("INSERT INTO query_log (question, status, user_id) VALUES ('Is it legal?', 'ANSWERED', %s)", (uid,))
    clean_db.init_db()
    with clean_db.connect() as con:
        assert sorted(u["email"] for u in con.execute("SELECT email FROM users").fetchall()) == \
            ["boss@example.com", "reader@example.com"]
        assert con.execute("SELECT user_id FROM query_log").fetchone()["user_id"] == uid
        con.execute("DELETE FROM query_log")
        con.execute("DELETE FROM users WHERE role = 'user'")
        con.execute("ALTER TABLE users DROP CONSTRAINT users_role_check")            # a database from step 5.11
        con.execute("ALTER TABLE users ADD CONSTRAINT users_role_check CHECK (role IN ('admin'))")
    clean_db.init_db()
    assert clean_db.create_visitor("new@example.com", PW) is not None


