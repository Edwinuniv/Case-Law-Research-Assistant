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


def test_only_the_administrator_role_exists(clean_db):                              # SR33
    """SR33: two roles, the visitor (no account at all) and the administrator. So an account is
    always an administrator, and no 'user' account can be created."""
    clean_db.create_user("boss@example.com", PW)                     # admin by default (seed.py)
    boss, _ = clean_db.check_login("boss@example.com", PW)
    assert boss["role"] == "admin" and clean_db.user_is_active_admin(boss["id"])
    with pytest.raises(ValueError):
        clean_db.create_user("reader@example.com", PW, role="user")
    with clean_db.connect() as con:                                  # the database refuses it too
        with pytest.raises(Exception):
            con.execute("INSERT INTO users (email, password_hash, role) VALUES ('r@example.com', 'x', 'user')")


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


def test_existing_database_loses_the_user_accounts(clean_db):
    """A database made during steps 5.6-5.10 allows 'user' accounts (Joe's PC, maybe Railway).
    init_db must remove them, keep their questions in the log (FR28) and keep the administrators."""
    clean_db.create_user("boss@example.com", PW)
    with clean_db.connect() as con:                                  # the database as it was in 5.6-5.10
        con.execute("ALTER TABLE users DROP CONSTRAINT users_role_check")
        con.execute("ALTER TABLE users ADD CONSTRAINT users_role_check CHECK (role IN ('admin', 'user'))")
        uid = con.execute("INSERT INTO users (email, password_hash, role) VALUES ('reader@example.com', 'x', 'user') "
                          "RETURNING id").fetchone()["id"]
        con.execute("INSERT INTO query_log (question, status, user_id) VALUES ('Is it legal?', 'ANSWERED', %s)", (uid,))
    clean_db.init_db()
    with clean_db.connect() as con:
        assert [u["email"] for u in con.execute("SELECT email FROM users").fetchall()] == ["boss@example.com"]
        log = con.execute("SELECT question, user_id FROM query_log").fetchall()
        assert log == [{"question": "Is it legal?", "user_id": None}]
    with pytest.raises(ValueError):
        clean_db.create_user("reader@example.com", PW, role="user")
