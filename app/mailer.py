"""Sending an email (Edwin, SPEC 11, 2026-11-19): only the forgot-password link for now.
Through Resend's HTTPS API when RESEND_API_KEY and MAIL_FROM are set (Railway blocks SMTP on the Hobby plan).
Without them: printed in the server's console on a local computer, to test; never printed online (HTTPS_ONLY=1),
because the console of the deployed site is a log other people may read."""
import httpx
from app import config


def send(to, subject, text):
    """True if the email went out (or was printed locally), False otherwise. Never raises."""
    if config.RESEND_API_KEY and config.MAIL_FROM:
        try:
            r = httpx.post("https://api.resend.com/emails", timeout=10,
                           headers={"Authorization": f"Bearer {config.RESEND_API_KEY}"},
                           json={"from": config.MAIL_FROM, "to": [to], "subject": subject, "text": text})
            return r.status_code < 300
        except httpx.HTTPError:
            return False
    if config.HTTPS_ONLY:
        print("Email not set up (RESEND_API_KEY, MAIL_FROM): nothing sent.")
        return False
    print(f"--- email NOT sent (no RESEND_API_KEY), printed for testing ---\nTo: {to}\nSubject: {subject}\n{text}\n---")
    return True
