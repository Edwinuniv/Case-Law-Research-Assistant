"""Every email Verdicta sends, in one design (Edwin, SPEC 11, 2026-11-20, rule 5).
The look of the site: a dark header with the logo and the gold line, a white card, a gold button, a box for a code,
the team's signature and the "not legal advice" footer. Built with tables and inline styles, the HTML that mail
programs (Gmail, Outlook, phones) show the same way; every email also has a plain-text copy. Everything a user typed
is escaped (html.escape), so a message can never add HTML or a link of its own.
Each function below builds one email and hands it to mailer.send_later (sent after the answer, never blocking it)."""
from html import escape
from app import config, mailer

SERIF = "Georgia,'Times New Roman',serif"
SANS = "-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
TEAM = "Yasser Hajj Youssef · Edwin Mouawad · Joe Bou Karam"
ACCOUNT_NOTE = "You receive this email because it is about your Verdicta account."


def url(path):
    return config.PUBLIC_URL.rstrip("/") + path


def render(title, paragraphs, button=None, code=None, details=None, note=ACCOUNT_NOTE):
    """(html, text) of one email. button: (label, path); details: [(label, value)]; all texts are plain text."""
    e = escape
    parts = [f'<h1 style="margin:0 0 18px;font:400 26px/1.25 {SERIF};color:#121216">{e(title)}</h1>']
    parts += [f'<p style="margin:0 0 14px;font:15px/1.65 {SANS};color:#3a3a40">{e(p)}</p>' for p in paragraphs]
    if code:
        parts.append(f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:22px 0 8px">'
                     f'<tr><td align="center" style="background:#fbf6ea;border:1px solid #f0d9a8;border-radius:14px;'
                     f'padding:22px 10px;font:700 34px/1 Menlo,Consolas,monospace;letter-spacing:10px;color:#121216">'
                     f'{e(code)}</td></tr></table>')
    if details:
        rows = "".join(f'<tr><td style="padding:10px 0;border-bottom:1px solid #f0ede6;font:14px {SANS};color:#8a847c">'
                       f'{e(k)}</td><td style="padding:10px 0;border-bottom:1px solid #f0ede6;font:600 14px {SANS};'
                       f'color:#121216;text-align:right">{e(v)}</td></tr>' for k, v in details)
        parts.append(f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                     f'style="margin:8px 0 18px;background:#faf8f4;border-radius:12px;padding:6px 16px">{rows}</table>')
    if button:
        label, path = button
        parts.append(f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:24px 0 8px"><tr>'
                     f'<td style="background:#f59e0b;border-radius:999px"><a href="{e(url(path))}" '
                     f'style="display:inline-block;padding:14px 30px;font:700 15px {SANS};color:#141418;'
                     f'text-decoration:none">{e(label)}</a></td></tr></table>')
    logo = e(url("/assets/email-logo.png"))
    html = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<meta name="color-scheme" content="light"><title>{e(title)}</title></head>
<body style="margin:0;padding:0;background:#efece5">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#efece5;padding:28px 12px">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;
border-radius:18px;overflow:hidden;box-shadow:0 12px 40px rgba(20,20,24,.10)">
<tr><td style="background:#141418;padding:26px 40px;border-bottom:3px solid #f59e0b">
<table role="presentation" cellpadding="0" cellspacing="0"><tr>
<td style="padding-right:12px"><img src="{logo}" width="52" height="45" alt="" style="display:block;border:0"></td>
<td><div style="font:600 24px/1 {SERIF};color:#ffffff;letter-spacing:.04em">Verdicta</div>
<div style="margin-top:6px;font:600 10.5px/1 {SANS};color:#fbbf24;letter-spacing:.24em;text-transform:uppercase">Verified case-law research</div></td>
</tr></table></td></tr>
<tr><td style="padding:36px 40px 10px">{"".join(parts)}</td></tr>
<tr><td style="padding:10px 40px 30px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0"
style="border-top:1px solid #eeeae2"><tr><td style="padding-top:20px;font:14px/1.6 {SANS};color:#3a3a40">
Kind regards,<br><span style="font:600 17px/1.8 {SERIF};color:#121216">The Verdicta team</span><br>
<span style="font-size:12.5px;color:#8a847c">{e(TEAM)}</span><br>
<a href="mailto:{e(config.TEAM_EMAIL)}" style="color:#b45309;text-decoration:none">{e(config.TEAM_EMAIL)}</a>
&nbsp;·&nbsp;<a href="{e(url("/"))}" style="color:#b45309;text-decoration:none">{e(url("/").split("//")[-1].rstrip("/"))}</a>
</td></tr></table></td></tr>
<tr><td style="background:#f7f5f0;padding:20px 40px;font:12px/1.6 {SANS};color:#8a847c;text-align:center">
{e(note)}<br>Verdicta is a student project of ESIB, Université Saint-Joseph. This is a research aid, not legal advice.<br>
<a href="{e(url("/privacy"))}" style="color:#8a847c">Privacy</a> · <a href="{e(url("/terms"))}" style="color:#8a847c">Terms</a>
· <a href="{e(url("/contact"))}" style="color:#8a847c">Contact</a></td></tr>
</table></td></tr></table></body></html>"""
    text = [title, ""] + [p for p in paragraphs for p in (p, "")]
    if code:
        text += [f"Your code: {code}", ""]
    for k, v in details or []:
        text.append(f"{k}: {v}")
    if details:
        text.append("")
    if button:
        text += [f"{button[0]}: {url(button[1])}", ""]
    text += ["Kind regards,", "The Verdicta team", TEAM, f"{config.TEAM_EMAIL} · {url('/')}", "", note,
             "This is a research aid, not legal advice."]
    return html, "\n".join(text)


def deliver(to, subject, title, paragraphs, reply_to=None, **parts):
    html, text = render(title, paragraphs, **parts)
    mailer.send_later(to, subject, text, html, reply_to)


# ---------------- the emails ----------------
def verification_code(to, code, minutes):
    deliver(to, "Your Verdicta verification code", "Confirm your email",
            ["Welcome to Verdicta. To finish creating your account, type this code on the verification page.",
             f"It works for {minutes} minutes."], code=code,
            note="If you did not create a Verdicta account, you can ignore this email: nothing happens without the code.")


def reset_link(to, path, minutes):
    deliver(to, "Reset your Verdicta password", "Choose a new password",
            ["Someone asked to reset the password of your Verdicta account.",
             f"The button below works once, for {minutes} minutes."], button=("Choose a new password", path),
            note="If it was not you, ignore this email: your password stays the same.")


def welcome(to):
    deliver(to, "Welcome to Verdicta", "Your email is verified",
            ["Your Verdicta account is ready. Ask a question about a U.S. Supreme Court decision (2000-2024): every "
             "citation and every quote in the answer is checked against the opinion itself before you see it.",
             "Your questions are saved in your account, so you find them again under \"My chats\"."],
            button=("Ask a question", "/research"))


def password_changed(to, how="with a reset link"):
    deliver(to, "Your Verdicta password was changed", "Your password was changed",
            [f"The password of your Verdicta account has just been changed {how}.",
             "If it was you, there is nothing to do. If it was not, ask for a new reset link at once and tell us."],
            button=("Log in", "/login"))


def plan_changed(to, plan, daily_limit):
    name = "Paid" if plan == "paid" else "Free"
    deliver(to, f"Your Verdicta plan is now {name}", f"Your plan is now {name}",
            [f"Your account is on the {name} plan from now on.",
             "Payments run in Stripe's test mode for this student project: no real money moves."],
            details=[("Plan", name), ("Questions a day", str(daily_limit)), ("The day starts", "midnight, Beirut time")],
            button=("See your plan", "/pricing"))


def account_status(to, active):
    if active:
        deliver(to, "Your Verdicta account was enabled", "Your account is enabled again",
                ["An administrator has enabled your Verdicta account again: you can log in as before."],
                button=("Log in", "/login"))
    else:
        deliver(to, "Your Verdicta account was disabled", "Your account was disabled",
                ["An administrator has disabled your Verdicta account: you cannot log in for now.",
                 "If you think this is a mistake, write to us from the contact page or answer this email."],
                button=("Contact us", "/contact"))


def account_deleted(to):
    deliver(to, "Your Verdicta account was deleted", "Your account was deleted",
            ["As you asked, your Verdicta account has been deleted, with your questions, chats and ratings.",
             "You can still use Verdicta without an account, or create a new one at any time."],
            button=("Open Verdicta", "/"),
            note="This is the last email about this account.")


def contact_to_team(recipients, name, sender, text):
    """A contact message, to every team address; Reply-To is the visitor, who gets no email from us."""
    name = " ".join(name.split())                            # one line: it goes in the subject
    for to in recipients:
        deliver(to, f"Contact form: {name}", "A new message from the contact form", text.splitlines() or [text],
                reply_to=sender, details=[("Name", name), ("Email", sender)],
                note="Sent from the contact form of Verdicta. Reply to this email to answer the visitor.")
