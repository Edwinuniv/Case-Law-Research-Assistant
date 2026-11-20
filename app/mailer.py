"""Sending an email from the team's Gmail account (Edwin, SPEC 11, 2026-11-19, changed 2026-11-20).
Three ways, the first one set up is used (transport()):
- "gmail": the Gmail API over HTTPS, the way that works on Railway (it blocks SMTP on the Hobby plan). The OAuth
  client (GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET) and the account's refresh token (GMAIL_REFRESH_TOKEN, made once with
  scripts/gmail_token.py) give a short-lived access token, kept until it expires.
- "smtp": Gmail's SMTP server with an app password (SMTP_USER, SMTP_PASSWORD), simpler on a laptop.
- "console": printed in the server's console, only on a local computer (never online: HTTPS_ONLY=1), to test.
send() never raises: an email that cannot go out is only written to the server's log, the visitor's request goes on."""
import base64
import re
import smtplib
import threading
import time
from email.message import EmailMessage
from email.utils import formataddr
import httpx
from app import config

ADDRESS = re.compile(r"[^@\s<>,;]+@[^@\s<>,;]+\.[^@\s<>,;]+")
_token = {}                                  # the Gmail access token and when it expires


def transport():
    if config.GMAIL_CLIENT_ID and config.GMAIL_CLIENT_SECRET and config.GMAIL_REFRESH_TOKEN:
        return "gmail"
    if config.SMTP_USER and config.SMTP_PASSWORD:
        return "smtp"
    return None if config.HTTPS_ONLY else "console"


def message(to, subject, text, html=None, reply_to=None):
    msg = EmailMessage()
    msg["From"] = formataddr(("Verdicta", config.TEAM_EMAIL))
    msg["To"] = to
    msg["Subject"] = subject
    if reply_to and ADDRESS.fullmatch(reply_to):            # one plain address, or no Reply-To at all
        msg["Reply-To"] = reply_to
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")             # mail programs show the HTML, or else the text
    return msg


def gmail_access_token():
    if _token.get("expires", 0) > time.time() + 60:
        return _token["value"]
    r = httpx.post("https://oauth2.googleapis.com/token", timeout=10, data={
        "client_id": config.GMAIL_CLIENT_ID, "client_secret": config.GMAIL_CLIENT_SECRET,
        "refresh_token": config.GMAIL_REFRESH_TOKEN, "grant_type": "refresh_token"})
    if r.status_code != 200:
        raise RuntimeError(f"Gmail token refused ({r.status_code})")
    data = r.json()
    _token.update(value=data["access_token"], expires=time.time() + int(data.get("expires_in", 3600)))
    return _token["value"]


def send(to, subject, text, html=None, reply_to=None):
    """True if the email went out (or was printed locally), False otherwise. Never raises."""
    how = transport()
    msg = message(to, subject, text, html, reply_to)
    try:
        if how == "gmail":
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            r = httpx.post("https://gmail.googleapis.com/gmail/v1/users/me/messages/send", timeout=15,
                           headers={"Authorization": f"Bearer {gmail_access_token()}"}, json={"raw": raw})
            if r.status_code >= 300:
                raise RuntimeError(f"Gmail refused the email ({r.status_code})")
        elif how == "smtp":
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
                server.send_message(msg)
        elif how == "console":
            print(f"--- email NOT sent (no mail account set up), printed for testing ---\n"
                  f"To: {to}\nSubject: {subject}\n{text}\n---")
        else:
            print(f"Email not set up (GMAIL_* or SMTP_*): nothing sent ({subject}).")
            return False
        return True
    except (httpx.HTTPError, smtplib.SMTPException, OSError, RuntimeError, KeyError, ValueError) as e:
        print(f"Email to {to} not sent ({subject}): {e}")
        return False


def send_later(to, subject, text, html=None, reply_to=None):
    """Sends in the background, so the visitor's request never waits for Gmail."""
    threading.Thread(target=send, args=(to, subject, text, html, reply_to), daemon=True).start()
