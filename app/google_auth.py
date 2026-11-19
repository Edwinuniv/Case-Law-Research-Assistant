"""Sign in with Google (Yasser, SPEC section 11, 2026-11-13).

The browser shows Google's button (Google Identity Services). After the person chooses their Google account, Google
gives the browser an ID token: a short text signed by Google that says "this is reader@example.com, made for the
website with client id X, valid until T". The browser sends it to POST /api/auth/google (app/api.py), and this file
checks it with Google's public keys before we trust the email. We store nothing from Google except the email.

GOOGLE_CLIENT_ID comes from the Google Cloud console (APIs & Services > Credentials > OAuth client ID, type "Web
application"). It is public (it is in the page), so it is not a secret; no client secret is needed for this flow."""
import os

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app import config  # noqa: F401  (loads .env, so GOOGLE_CLIENT_ID is read even when this file is imported first)

CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()     # empty: no Google button, the route answers 404
_transport = google_requests.Request()                         # downloads and caches Google's public keys


def enabled():
    return bool(CLIENT_ID)


def verify_credential(credential):
    """The verified email (lower case) in a Google ID token, or ValueError.
    verify_oauth2_token checks the signature with Google's keys, that the token was made for OUR client id
    (audience), that Google issued it (accounts.google.com) and that it has not expired."""
    info = id_token.verify_oauth2_token(credential, _transport, CLIENT_ID)
    if not info.get("email") or info.get("email_verified") is not True:
        raise ValueError("Google did not verify this email")
    return info["email"].lower().strip()
