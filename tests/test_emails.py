"""The emails' design and how they are sent (SPEC 11, 2026-11-20, rules 1 and 5), written from the rule before the
code. No real email: httpx.post and smtplib are replaced by fakes."""
import base64
import email
import pytest
from app import config, emails, mailer


@pytest.fixture
def no_transport(monkeypatch):
    for k in ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN", "SMTP_USER", "SMTP_PASSWORD"):
        monkeypatch.setattr(config, k, "")
    monkeypatch.setattr(config, "PUBLIC_URL", "https://verdicta.example")


def test_the_template_has_the_logo_signature_footer_and_a_text_copy(no_transport):
    html, text = emails.render("Welcome to Verdicta", ["Your email is verified."], button=("Ask a question", "/research"))
    assert "https://verdicta.example/assets/email-logo.png" in html          # the logo, from the site itself
    assert "The Verdicta team" in html and "verdicta.team@gmail.com" in html  # the signature
    assert "not legal advice" in html                                        # the footer
    assert 'href="https://verdicta.example/research"' in html               # links on the site's own address
    assert "Welcome to Verdicta" in text and "Your email is verified." in text and "<" not in text
    assert "https://verdicta.example/research" in text and "The Verdicta team" in text


def test_everything_a_user_typed_is_escaped(no_transport):
    html, _ = emails.render("Message", ['<script>alert(1)</script> & "x"'])
    assert "<script>" not in html and "&lt;script&gt;" in html and "&amp;" in html


def test_the_code_is_shown_in_its_own_box_and_in_the_text(no_transport):
    html, text = emails.render("Your code", ["Type this code."], code="482913")
    assert "482913" in html and "482913" in text
    assert html.count("482913") == 1                                         # one box, not repeated in the title


def test_the_transport_is_gmail_then_smtp_then_the_console_locally(no_transport, monkeypatch):
    monkeypatch.setattr(config, "HTTPS_ONLY", False)
    assert mailer.transport() == "console"
    monkeypatch.setattr(config, "HTTPS_ONLY", True)
    assert mailer.transport() is None                                        # online: never printed
    monkeypatch.setattr(config, "SMTP_USER", "verdicta.team@gmail.com")
    monkeypatch.setattr(config, "SMTP_PASSWORD", "app-password")
    assert mailer.transport() == "smtp"
    for k in ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN"):
        monkeypatch.setattr(config, k, "x")
    assert mailer.transport() == "gmail"


class Response:
    def __init__(self, status, data=None):
        self.status_code, self._data = status, data or {}

    def json(self):
        return self._data


@pytest.fixture
def gmail(no_transport, monkeypatch):
    """The Gmail API, faked: the token request, then the send request with the whole message."""
    for k in ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN"):
        monkeypatch.setattr(config, k, f"{k.lower()}-value")
    monkeypatch.setattr(mailer, "_token", {})                               # no access token kept from another test
    calls = []

    def post(url, **kw):
        calls.append((url, kw))
        if "oauth2" in url:
            return Response(200, {"access_token": "tok", "expires_in": 3600})
        return Response(200, {"id": "abc"})
    monkeypatch.setattr(mailer.httpx, "post", post)
    return calls


def test_gmail_sends_the_html_and_text_from_the_team_address(gmail):
    assert mailer.send("reader@example.com", "Your code", "text part", "<p>html part</p>",
                       reply_to="visitor@example.com") is True
    (token_url, token), (send_url, sent) = gmail
    assert "oauth2.googleapis.com/token" in token_url and token["data"]["grant_type"] == "refresh_token"
    assert "gmail.googleapis.com/gmail/v1/users/me/messages/send" in send_url
    assert sent["headers"]["Authorization"] == "Bearer tok"
    msg = email.message_from_bytes(base64.urlsafe_b64decode(sent["json"]["raw"]))
    assert msg["To"] == "reader@example.com" and "verdicta.team@gmail.com" in msg["From"]
    assert msg["Reply-To"] == "visitor@example.com" and msg["Subject"] == "Your code"
    parts = {p.get_content_type(): p.get_payload(decode=True).decode() for p in msg.walk() if not p.is_multipart()}
    assert parts == {"text/plain": "text part\n", "text/html": "<p>html part</p>\n"}


def test_the_access_token_is_kept_until_it_expires(gmail):
    mailer.send("a@example.com", "One", "t")
    mailer.send("b@example.com", "Two", "t")
    assert sum(1 for url, _ in gmail if "oauth2" in url) == 1


def test_a_failed_send_returns_false_and_never_raises(gmail, monkeypatch):
    def broken(url, **kw):
        raise mailer.httpx.ConnectError("no network")
    monkeypatch.setattr(mailer.httpx, "post", broken)
    assert mailer.send("a@example.com", "Hi", "t") is False
    monkeypatch.setattr(mailer.httpx, "post", lambda url, **kw: Response(403))
    assert mailer.send("a@example.com", "Hi", "t") is False


@pytest.mark.parametrize("bad", ["a@example.com\nBcc: x@example.com", "not an address", ""])
def test_a_reply_to_that_is_not_one_address_is_dropped(gmail, bad):
    mailer.send("a@example.com", "Hi", "t", reply_to=bad)
    msg = email.message_from_bytes(base64.urlsafe_b64decode(gmail[-1][1]["json"]["raw"]))
    assert msg["Reply-To"] is None and msg["Bcc"] is None


def test_smtp_logs_in_with_the_app_password(no_transport, monkeypatch):
    monkeypatch.setattr(config, "SMTP_USER", "verdicta.team@gmail.com")
    monkeypatch.setattr(config, "SMTP_PASSWORD", "app-password")
    seen = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            seen["server"] = (host, port)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def login(self, user, password):
            seen["login"] = (user, password)

        def send_message(self, msg):
            seen["to"] = msg["To"]
    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", FakeSMTP)
    assert mailer.send("reader@example.com", "Hi", "t") is True
    assert seen == {"server": ("smtp.gmail.com", 465), "login": ("verdicta.team@gmail.com", "app-password"),
                    "to": "reader@example.com"}
