"""Forgot password by email, and error messages that reveal nothing (SPEC 11, 2026-11-19).
Written from the rule in SPEC before the code. No real email: mailer.send is replaced by a list. TEST database."""
import hashlib
import pytest
from fastapi.testclient import TestClient

PW, NEW = "a-long-password", "a-brand-new-password"
SAME_ANSWER = "If an account exists for this email"
BAD_LINK = "This link is not valid any more. Ask for a new one."


@pytest.fixture
def sent(monkeypatch):
    """Every email the site sends: (to, subject, text)."""
    from app import mailer
    out = []
    monkeypatch.setattr(mailer, "send", lambda to, subject, text: out.append((to, subject, text)) or True)
    return out


@pytest.fixture
def c(clean_db, monkeypatch, sent):
    from app import api, api_site, config, main
    monkeypatch.setattr(main, "load_index", lambda: None)
    monkeypatch.setattr(config, "PUBLIC_URL", "https://verdicta.example")
    api.FAILED_BY_IP.clear()
    api_site.RESETS_BY_IP.clear()
    clean_db.create_visitor("reader@example.com", PW)
    with TestClient(main.app) as client:
        yield client


def csrf(c):
    return {"X-CSRF-Token": c.get("/api/me").json()["csrf"]}


def forgot(c, email="reader@example.com", headers=None):
    return c.post("/api/password/forgot", json={"email": email}, headers={**csrf(c), **(headers or {})})


def reset(c, token, password=NEW):
    return c.post("/api/password/reset", json={"token": token, "password": password}, headers=csrf(c))


def token_in(mail):
    return mail[2].split("/reset?token=")[1].split()[0]


def log_in(c, email="reader@example.com", password=NEW):
    return c.post("/api/login", json={"email": email, "password": password}, headers=csrf(c))


def test_a_user_gets_a_link_and_an_unknown_email_gets_the_same_answer(c, sent):          # rule 1
    known, unknown = forgot(c), forgot(c, "nobody@example.com")
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json() and SAME_ANSWER in known.json()["message"]
    assert [m[0] for m in sent] == ["reader@example.com"]                                # only the real account


@pytest.mark.parametrize("who", ["admin", "disabled"])
def test_no_email_for_an_administrator_or_a_disabled_account(c, clean_db, sent, who):     # rule 1
    if who == "admin":
        clean_db.create_user("boss@example.com", PW)
        email = "boss@example.com"
    else:
        email = "reader@example.com"
        with clean_db.connect() as con:
            con.execute("UPDATE users SET active = FALSE WHERE email = %s", (email,))
    r = forgot(c, email)
    assert r.status_code == 200 and SAME_ANSWER in r.json()["message"]
    assert sent == []


def test_the_link_uses_public_url_never_the_host_header(c, sent):                          # rule 2
    forgot(c, headers={"Host": "evil.example", "X-Forwarded-Host": "evil.example"})
    assert sent and "https://verdicta.example/reset?token=" in sent[0][2]
    assert "evil.example" not in sent[0][2]


def test_only_a_hash_of_the_token_is_stored(c, clean_db, sent):                            # rule 2
    forgot(c)
    token = token_in(sent[0])
    with clean_db.connect() as con:
        rows = con.execute("SELECT * FROM password_resets").fetchall()
    assert len(rows) == 1 and token not in str(rows)
    assert hashlib.sha256(token.encode()).hexdigest() in str(rows)


def test_the_link_changes_the_password_once(c, clean_db, sent):                            # rule 3
    forgot(c)
    token = token_in(sent[0])
    assert reset(c, token).status_code == 200
    assert log_in(c).status_code == 200                                                    # the new password works
    c.post("/api/logout", headers=csrf(c))
    assert log_in(c, password=PW).status_code == 401                                       # the old one does not
    again = reset(c, token, "yet-another-password")
    assert again.status_code == 400 and again.json()["detail"] == BAD_LINK                 # used once only


def test_a_wrong_or_expired_link_gives_one_message_and_changes_nothing(c, clean_db, sent):  # rule 3
    forgot(c)
    token = token_in(sent[0])
    with clean_db.connect() as con:
        con.execute("UPDATE password_resets SET expires_at = now() - interval '1 minute'")
    for t in (token, "not-a-real-token", ""):
        r = reset(c, t)
        assert r.status_code == 400 and r.json()["detail"] == BAD_LINK
    assert log_in(c, password=PW).status_code == 200                                       # password unchanged


def test_a_short_password_is_refused_and_the_link_still_works(c, sent):                    # rule 3
    forgot(c)
    token = token_in(sent[0])
    assert reset(c, token, "short").status_code == 400
    assert reset(c, token).status_code == 200


def test_a_reset_unlocks_the_account_and_is_logged(c, clean_db, sent):                     # rule 3
    with clean_db.connect() as con:
        con.execute("UPDATE users SET failed_logins = 4, locked_until = now() + interval '10 minutes'")
    forgot(c)
    assert reset(c, token_in(sent[0])).status_code == 200
    assert log_in(c).status_code == 200                                                    # no longer locked
    with clean_db.connect() as con:
        events = [r["event"] for r in con.execute("SELECT event FROM user_log ORDER BY id").fetchall()]
        left = con.execute("SELECT count(*) AS n FROM password_resets").fetchone()["n"]
    assert "password_reset" in events and left == 0                                        # every token deleted


def test_one_email_per_account_in_two_minutes(c, sent):                                    # rule 1
    forgot(c)
    r = forgot(c)
    assert r.status_code == 200 and SAME_ANSWER in r.json()["message"]                     # same answer...
    assert len(sent) == 1                                                                  # ...but no second email


def test_five_asks_per_address_then_429(c, sent):                                          # rule 1
    for i in range(5):
        assert forgot(c, f"someone{i}@example.com").status_code == 200
    assert forgot(c, "someone5@example.com").status_code == 429


def test_without_resend_the_link_is_printed_locally_but_never_online(monkeypatch, capsys):  # rule 4
    from app import config, mailer
    monkeypatch.setattr(config, "RESEND_API_KEY", "")
    monkeypatch.setattr(config, "HTTPS_ONLY", False)
    mailer.send("a@example.com", "Reset", "Open https://x/reset?token=abc123")
    assert "abc123" in capsys.readouterr().out
    monkeypatch.setattr(config, "HTTPS_ONLY", True)
    assert mailer.send("a@example.com", "Reset", "Open https://x/reset?token=def456") is False
    assert "def456" not in capsys.readouterr().out


def test_a_badly_formed_request_does_not_echo_what_was_sent(c):                            # rule 5
    r = c.post("/api/login", json={"email": "reader@example.com", "pasword": "my-secret-password"}, headers=csrf(c))
    assert r.status_code == 422 and r.json() == {"detail": "Some fields are missing or not valid."}
    assert "my-secret-password" not in r.text and "reader@example.com" not in r.text


def test_an_unexpected_error_shows_no_technical_detail(clean_db, monkeypatch):             # rule 5
    from app import api, main
    monkeypatch.setattr(main, "load_index", lambda: None)

    def broken(email):
        raise RuntimeError("password_hash column, /home/edwin/app/db.py line 42")
    monkeypatch.setattr(api.db, "account_for_log", broken)
    with TestClient(main.app, raise_server_exceptions=False) as client:
        r = client.post("/api/login", json={"email": "a@example.com", "password": PW},
                        headers={"X-CSRF-Token": client.get("/api/me").json()["csrf"]})
    assert r.status_code == 500 and r.json() == {"detail": "Something went wrong on our side. Please try again."}
    assert "db.py" not in r.text and "password_hash" not in r.text and "Traceback" not in r.text
