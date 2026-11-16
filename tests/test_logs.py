"""The two logs (SPEC section 11, 2026-11-13; part 3 of docs/PLAN_2026-11-13.md): written from the rule in SPEC.
User log: what an account does. Admin log: what administrators do. Fake search and model; TEST database."""
import pytest
from tests.test_api_research import c as research_client, csrf, ask   # noqa: F401  (the fixture is used below)

PW = "a-long-password"


@pytest.fixture
def c(research_client, clean_db):
    from app import api
    api.SIGNUPS_BY_IP.clear()
    api.FAILED_BY_IP.clear()
    clean_db.create_user("boss@example.com", PW)                      # an administrator
    return research_client


def post(c, path, body=None):
    return c.post(path, json=body or {}, headers=csrf(c))


def log_in(c, email, password=PW):
    return post(c, "/api/login", {"email": email, "password": password})


def user_events(db, email):
    with db.connect() as con:
        return [r["event"] for r in con.execute(
            "SELECT event FROM user_log l JOIN users u ON u.id = l.user_id WHERE u.email = %s ORDER BY l.id", (email,))]


def admin_actions(db):
    with db.connect() as con:
        return [(r["admin_email"], r["action"], r["status"]) for r in con.execute(
            "SELECT admin_email, action, status FROM admin_log ORDER BY id")]


def test_a_users_actions_go_to_their_log_in_order(c, clean_db):            # rule 1
    post(c, "/api/signup", {"email": "reader@example.com", "password": PW})
    shown = ask(c).json()
    post(c, "/api/logout")
    log_in(c, "reader@example.com", "a-wrong-password")
    log_in(c, "reader@example.com")
    assert user_events(clean_db, "reader@example.com") == ["signup", "question", "logout", "login_failed", "login"]
    with clean_db.connect() as con:                                       # the question row points to query_log
        q = con.execute("SELECT query_id, detail FROM user_log WHERE event = 'question'").fetchone()
        f = con.execute("SELECT detail FROM user_log WHERE event = 'login_failed'").fetchone()
    assert q["query_id"] == shown["id"] and q["detail"]["status"] == shown["status"]
    assert f["detail"] == {"reason": "wrong password"}
    assert admin_actions(clean_db) == []                                  # nothing in the admin log


def test_a_refusal_is_logged_with_its_reason(c, clean_db, monkeypatch):    # rule 1: refused
    from app import api
    post(c, "/api/signup", {"email": "reader@example.com", "password": PW})
    monkeypatch.setattr(api, "seconds_to_wait", lambda ip: 42)            # the per-minute limit says no
    assert ask(c).status_code == 429
    with clean_db.connect() as con:
        r = con.execute("SELECT event, detail FROM user_log ORDER BY id DESC LIMIT 1").fetchone()
    assert r["event"] == "refused" and r["detail"]["reason"] == "questions per minute"


def test_visitors_without_an_account_have_no_user_log(c, clean_db):         # rule 1 (FR28 still logs the question)
    ask(c)
    with clean_db.connect() as con:
        assert con.execute("SELECT count(*) AS n FROM user_log").fetchone()["n"] == 0
        assert con.execute("SELECT count(*) AS n FROM query_log").fetchone()["n"] == 1


def test_admin_login_changes_exports_and_logout_go_to_the_admin_log(c, clean_db):   # rule 2
    log_in(c, "boss@example.com", "a-wrong-password")
    log_in(c, "boss@example.com")
    c.get("/api/admin/settings")                                          # only reads: not logged
    post(c, "/api/admin/settings", {"tau_abstain": 0.3, "tau_confident": 0.6, "min_retrieval": 0.3,
                                    "top_k": 8, "retrieve_k": 20, "use_reranker": False})   # a change
    c.get("/api/admin/questions/export")                                  # an export: logged
    post(c, "/api/logout")
    actions = admin_actions(clean_db)
    assert [a for _, a, _ in actions] == ["login_failed", "login", "POST /api/admin/settings",
                                          "GET /api/admin/questions/export", "logout"]
    assert all(e == "boss@example.com" for e, _, _ in actions)
    assert actions[2][2] == 200                                           # the answer's status is kept


def test_an_admin_action_on_an_account_names_that_account(c, clean_db):    # rule 2
    uid = clean_db.create_visitor("reader@example.com", PW)
    log_in(c, "boss@example.com")
    post(c, f"/api/admin/users/{uid}/toggle")
    with clean_db.connect() as con:
        r = con.execute("SELECT target_user_id, action FROM admin_log ORDER BY id DESC LIMIT 1").fetchone()
    assert r["target_user_id"] == uid and r["action"] == f"POST /api/admin/users/{uid}/toggle"


def test_a_non_admin_knocking_on_admin_routes_is_not_an_admin_action(c, clean_db):
    post(c, "/api/signup", {"email": "reader@example.com", "password": PW})
    assert post(c, "/api/admin/settings", {"tau_abstain": 0.9}).status_code == 403
    assert admin_actions(clean_db) == []


def test_no_ip_or_password_is_stored(c, clean_db):                          # rule 4
    post(c, "/api/signup", {"email": "reader@example.com", "password": PW})
    log_in(c, "reader@example.com", "a-wrong-password")
    with clean_db.connect() as con:
        text = str(con.execute("SELECT * FROM user_log").fetchall()) + str(con.execute("SELECT * FROM admin_log").fetchall())
    assert "testclient" not in text and "127.0.0.1" not in text           # the test client's address
    assert PW not in text and "a-wrong-password" not in text


def test_only_admins_read_the_logs_as_json_or_csv(c, clean_db):            # rule 5
    uid = clean_db.create_visitor("reader@example.com", PW)
    assert c.get(f"/api/admin/users/{uid}/log").status_code == 401        # not logged in
    log_in(c, "reader@example.com")
    assert c.get(f"/api/admin/users/{uid}/log").status_code == 403        # a user, even for their own log
    post(c, "/api/logout")
    log_in(c, "boss@example.com")
    rows = c.get(f"/api/admin/users/{uid}/log").json()
    assert [r["event"] for r in rows] == ["logout", "login"]              # newest first
    f = c.get(f"/api/admin/users/{uid}/log?format=csv")
    assert f.headers["content-type"].startswith("text/csv") and "attachment" in f.headers["content-disposition"]
    assert f.text.splitlines()[0].startswith("id,at,event") and len(f.text.splitlines()) == 3
    assert c.get("/api/admin/users/99999/log").status_code == 404
    admin = c.get("/api/admin/log").json()                               # reading a log is itself logged, newest first
    assert admin[0]["action"] == "GET /api/admin/users/99999/log" and admin[0]["detail"] == {"target_not_found": 99999}
    assert admin[1]["action"] == f"GET /api/admin/users/{uid}/log" and admin[1]["target_user_id"] == uid


def test_the_user_log_goes_with_its_account(clean_db):                     # rule 5
    from app import logs
    uid = clean_db.create_visitor("reader@example.com", PW)
    logs.log_user(uid, "login")
    with clean_db.connect() as con:
        con.execute("DELETE FROM users WHERE id = %s", (uid,))
        assert con.execute("SELECT count(*) AS n FROM user_log").fetchone()["n"] == 0


def test_a_log_that_cannot_be_written_never_blocks_the_action(clean_db, capsys):   # rule 3
    from app import logs
    logs.log_user(99999, "login")                                         # no such account: the database refuses
    assert "could not write login" in capsys.readouterr().err
    with pytest.raises(ValueError):                                       # an unknown event is a programming mistake
        logs.log_user(1, "danced")


# ---- after Edwin's review of #96 (SPEC 11, the clarification of 2026-11-13) ----
def test_only_the_last_part_of_the_path_makes_a_logged_read():              # (c)
    from app import logs
    assert logs.logged_read("/api/admin/users/7/pdf") and logs.logged_read("/api/admin/log")
    assert logs.logged_read("/api/admin/questions/export/")
    assert not logs.logged_read("/api/admin/logins") and not logs.logged_read("/api/admin/exports-list")
    assert not logs.logged_read("/api/admin/log/summary")


def test_the_try_that_locks_the_account_says_so(c, clean_db):               # (b)
    post(c, "/api/signup", {"email": "reader@example.com", "password": PW})
    post(c, "/api/logout")
    for _ in range(6):                                                    # 5 wrong tries lock it (SR36), then a 6th
        log_in(c, "reader@example.com", "a-wrong-password")
    with clean_db.connect() as con:
        reasons = [r["detail"]["reason"] for r in con.execute(
            "SELECT detail FROM user_log WHERE event = 'login_failed' ORDER BY id")]
    assert reasons == ["wrong password"] * 4 + ["wrong password (account now locked)", "locked"]


def test_a_failed_login_on_an_admin_email_is_an_attempt_on_the_account(c, clean_db):   # (a)
    log_in(c, "boss@example.com", "a-wrong-password")                   # by anyone who knows the email
    with clean_db.connect() as con:
        r = con.execute("SELECT action, detail FROM admin_log").fetchone()
    assert r["action"] == "login_failed"
    assert r["detail"] == {"reason": "wrong password", "attempt_on_account": True}
