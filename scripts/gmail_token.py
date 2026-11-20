"""ONCE - Get the refresh token that lets the site send emails as verdicta.team@gmail.com (SPEC 11, 2026-11-20).
Needs GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET in .env: an OAuth client of type "Desktop app" in the Google Cloud
project, with the Gmail API enabled (README, "Emails"). The script opens a tiny web server on this computer, prints
Google's sign-in address; you open it, sign in AS verdicta.team@gmail.com and allow "send email on your behalf";
Google sends the browser back here with a one-time code, which the script trades for the refresh token.
Only the gmail.send permission is asked: the site can send, never read the mailbox.
Usage: python -m scripts.gmail_token     then put the printed GMAIL_REFRESH_TOKEN in .env and on Railway."""
import http.server
import secrets
import urllib.parse
import httpx
from app import config

SCOPE = "https://www.googleapis.com/auth/gmail.send"


def main():
    if not (config.GMAIL_CLIENT_ID and config.GMAIL_CLIENT_SECRET):
        raise SystemExit("Put GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET in .env first (README, 'Emails').")
    state, got = secrets.token_urlsafe(16), {}

    class Back(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            got.update(urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query))
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("Done: you can close this tab and go back to the terminal.".encode())

        def log_message(self, *args):                        # no request lines in the terminal
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Back)    # any free port
    redirect = f"http://127.0.0.1:{server.server_port}"
    print("Open this address in your browser and sign in as", config.TEAM_EMAIL, ":\n")
    print("https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": config.GMAIL_CLIENT_ID, "redirect_uri": redirect, "response_type": "code", "scope": SCOPE,
        "access_type": "offline", "prompt": "consent", "state": state}))
    while "code" not in got and "error" not in got:            # wait for Google to send the browser back
        server.handle_request()
    if got.get("state", [""])[0] != state or "error" in got:
        raise SystemExit(f"Refused or not our request: {got.get('error', ['wrong state'])[0]}")
    r = httpx.post("https://oauth2.googleapis.com/token", timeout=15, data={
        "code": got["code"][0], "client_id": config.GMAIL_CLIENT_ID, "client_secret": config.GMAIL_CLIENT_SECRET,
        "redirect_uri": redirect, "grant_type": "authorization_code"})
    token = r.json().get("refresh_token")
    if r.status_code != 200 or not token:
        raise SystemExit(f"Google did not give a refresh token ({r.status_code}): {r.text[:200]}")
    print("\nPut this line in .env (and the same variable on Railway). Keep it secret, like a password:\n")
    print(f"GMAIL_REFRESH_TOKEN={token}")


if __name__ == "__main__":
    main()
