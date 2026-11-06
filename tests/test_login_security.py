"""Login and roles in the database (SR33, SR34, SR36, step 5.6). Uses the TEST database."""
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


def test_user_role_and_admin_role(clean_db):                                        # SR33
    clean_db.create_user("reader@example.com", PW, role="user")
    clean_db.create_user("boss@example.com", PW)                     # admin by default (seed.py)
    reader, _ = clean_db.check_login("reader@example.com", PW)
    boss, _ = clean_db.check_login("boss@example.com", PW)
    assert reader["role"] == "user" and boss["role"] == "admin"
    assert clean_db.active_role(reader["id"]) == "user"
    assert not clean_db.user_is_active_admin(reader["id"])
    assert clean_db.user_is_active_admin(boss["id"])


def test_unknown_role_is_refused(clean_db):
    with pytest.raises(ValueError):
        clean_db.create_user("x@example.com", PW, role="superuser")
    with clean_db.connect() as con:
        assert con.execute("SELECT count(*) AS n FROM users").fetchone()["n"] == 0


def test_disabled_account_has_no_role(clean_db):
    clean_db.create_user("reader@example.com", PW, role="user")
    with clean_db.connect() as con:
        con.execute("UPDATE users SET active = FALSE")
        uid = con.execute("SELECT id FROM users").fetchone()["id"]
    assert clean_db.active_role(uid) is None
    assert clean_db.active_role(99999) is None                       # no such account


def test_existing_database_gets_the_user_role(clean_db):
    """A database made before step 5.6 only allows 'admin'; init_db must fix that (Joe's PC, Railway)."""
    with clean_db.connect() as con:
        con.execute("ALTER TABLE users DROP CONSTRAINT users_role_check")
        con.execute("ALTER TABLE users ADD CONSTRAINT users_role_check CHECK (role IN ('admin'))")
    clean_db.init_db()
    clean_db.create_user("reader@example.com", PW, role="user")
    with clean_db.connect() as con:
        assert con.execute("SELECT role FROM users").fetchone()["role"] == "user"
