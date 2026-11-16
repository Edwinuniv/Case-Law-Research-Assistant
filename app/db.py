"""PostgreSQL: connection, tables, and small helper functions."""
import json
import datetime
import bcrypt
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from app import config

SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'admin' CHECK (role IN ('admin', 'user')),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    failed_logins INT NOT NULL DEFAULT 0,
    locked_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now());

CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value JSONB NOT NULL);

CREATE TABLE IF NOT EXISTS chats (                 -- an account's saved chats (Joe, SPEC 11, 2026-11-14)
    id SERIAL PRIMARY KEY, user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE, title TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now());

CREATE TABLE IF NOT EXISTS decisions (
    decision_id INT PRIMARY KEY,            -- the cluster id we keep
    all_cluster_ids INT[] NOT NULL,         -- duplicates merged into this decision
    docket_id INT, docket_number TEXT,
    case_name TEXT NOT NULL, date_filed DATE NOT NULL,
    citations TEXT[] NOT NULL DEFAULT '{}',
    source_url TEXT,
    licence TEXT NOT NULL,                  -- SR11: no licence, no row
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now());

CREATE TABLE IF NOT EXISTS cluster_alias (
    cluster_id INT PRIMARY KEY,
    decision_id INT NOT NULL REFERENCES decisions ON DELETE CASCADE);

CREATE TABLE IF NOT EXISTS opinions (
    opinion_id INT PRIMARY KEY,
    decision_id INT NOT NULL REFERENCES decisions ON DELETE CASCADE,
    cluster_id INT, type TEXT, label TEXT, author TEXT,
    text TEXT NOT NULL, text_field TEXT, sha256 TEXT,
    licence TEXT NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now());

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    opinion_id INT NOT NULL REFERENCES opinions ON DELETE CASCADE,
    decision_id INT NOT NULL,
    ord INT, section TEXT, is_syllabus BOOLEAN,
    start_char INT, end_char INT, text TEXT NOT NULL,
    embedding vector(384));

CREATE TABLE IF NOT EXISTS citations (           -- SR12: every citation in CourtListener
    volume TEXT, reporter TEXT, page TEXT, cluster_id INT);

CREATE TABLE IF NOT EXISTS citation_map (        -- which of OUR opinions cites which opinion
    citing_opinion_id INT, cited_opinion_id INT, cited_cluster_id INT, depth INT);

CREATE TABLE IF NOT EXISTS ingestion_reports (   -- SR15
    id SERIAL PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    kind TEXT, report JSONB);

CREATE TABLE IF NOT EXISTS test_questions (      -- SR37, FR13
    id TEXT PRIMARY KEY,
    tag TEXT NOT NULL CHECK (tag IN ('answerable', 'unanswerable', 'adversarial')),
    split TEXT NOT NULL DEFAULT 'tune' CHECK (split IN ('tune', 'test')),
    question TEXT NOT NULL,
    expected_answer TEXT, gold_decision_ids INT[] NOT NULL DEFAULT '{}', gold_quote TEXT,
    must_not_appear TEXT[] NOT NULL DEFAULT '{}', why TEXT, author TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now());

CREATE TABLE IF NOT EXISTS query_log (           -- SR41, FR28
    id SERIAL PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    question TEXT, status TEXT, reason TEXT, support_score REAL, top_score REAL,
    n_sentences INT, n_removed INT, removed_citations JSONB, fabrications_caught INT,
    ms_search INT, ms_model INT, ms_total INT, details JSONB, label TEXT);

CREATE TABLE IF NOT EXISTS eval_runs (
    id SERIAL PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    trigger TEXT, status TEXT, settings JSONB, note TEXT);

CREATE TABLE IF NOT EXISTS eval_results (
    id SERIAL PRIMARY KEY,
    run_id INT NOT NULL REFERENCES eval_runs ON DELETE CASCADE,
    question_id TEXT, tag TEXT, split TEXT, result JSONB);

CREATE TABLE IF NOT EXISTS jobs (
    id SERIAL PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    kind TEXT, status TEXT, message TEXT);

CREATE TABLE IF NOT EXISTS contact_messages (      -- the contact form (Edwin, 2026-11-12); kept, see the privacy page
    id SERIAL PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    name TEXT NOT NULL, email TEXT NOT NULL, message TEXT NOT NULL);
-- the two logs (Yasser, SPEC section 11, 2026-11-13): written only through app/logs.py; no IP, no password
CREATE TABLE IF NOT EXISTS user_log (              -- everything an account does (shown in the user's details)
    id BIGSERIAL PRIMARY KEY, at TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event TEXT NOT NULL CHECK (event IN ('signup', 'login', 'login_failed', 'logout', 'question', 'follow_up',
                                         'plan_change', 'refused')),
    query_id INT REFERENCES query_log(id) ON DELETE SET NULL, detail JSONB NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS admin_log (             -- everything an administrator does
    id BIGSERIAL PRIMARY KEY, at TIMESTAMPTZ NOT NULL DEFAULT now(),
    admin_id INT REFERENCES users(id) ON DELETE SET NULL, admin_email TEXT NOT NULL,
    action TEXT NOT NULL, target_user_id INT REFERENCES users(id) ON DELETE SET NULL,
    status INT, detail JSONB NOT NULL DEFAULT '{}');

CREATE TABLE IF NOT EXISTS demo_answers (          -- saved answers to the example questions (Edwin, 2026-11-13)
    key TEXT PRIMARY KEY, question TEXT NOT NULL, result JSONB NOT NULL, shown JSONB NOT NULL,
    saved_at TIMESTAMPTZ NOT NULL DEFAULT now());
"""

INDEXES = """
CREATE INDEX IF NOT EXISTS citations_lookup ON citations (reporter, volume, page);
CREATE INDEX IF NOT EXISTS citation_map_citing ON citation_map (citing_opinion_id);
CREATE INDEX IF NOT EXISTS chunks_decision ON chunks (decision_id);
CREATE INDEX IF NOT EXISTS query_log_time ON query_log (created_at);
CREATE INDEX IF NOT EXISTS user_log_user ON user_log (user_id, at);
CREATE INDEX IF NOT EXISTS admin_log_time ON admin_log (at);
"""

# Changes to tables that already exist (CREATE TABLE IF NOT EXISTS does not change them).
# Safe to run at every start.
MIGRATIONS = """
-- 2026-11-06 (step 5.7): who asked each question (FR28 already saves the question)
ALTER TABLE query_log ADD COLUMN IF NOT EXISTS user_id INT REFERENCES users(id);
CREATE INDEX IF NOT EXISTS query_log_user ON query_log (user_id, id);
-- 2026-11-06 (step 5.11): only the administrator logged in, and this migration deleted every 'user' account.
-- 2026-11-12 (team decision, SPEC section 11): visitors may sign up again, so 'user' accounts are KEPT:
-- the delete is gone and the rule allows both roles. Safe to run at every start.
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users ADD CONSTRAINT users_role_check CHECK (role IN ('admin', 'user'));
-- 2026-11-14 (Joe, SPEC section 11): free and paid accounts; every account made before is free.
ALTER TABLE users ADD COLUMN IF NOT EXISTS plan TEXT NOT NULL DEFAULT 'free';
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_plan_check;
ALTER TABLE users ADD CONSTRAINT users_plan_check CHECK (plan IN ('free', 'paid'));
-- 2026-11-14 (Joe, SPEC section 11): each question of a saved chat; a deleted chat keeps its questions (FR28)
ALTER TABLE query_log ADD COLUMN IF NOT EXISTS chat_id INT REFERENCES chats(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS query_log_chat ON query_log (chat_id, id);
"""


def connect():
    """Use as: with db.connect() as con: ...  (commits automatically at the end)."""
    return psycopg.connect(config.DATABASE_URL, row_factory=dict_row)


def init_db():
    with connect() as con:
        con.execute(SCHEMA)
        con.execute(INDEXES)
        con.execute(MIGRATIONS)
        for key, value in config.DEFAULT_SETTINGS.items():
            con.execute("INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (key, Jsonb(value)))


# ---------------- settings ----------------
def get_settings():
    with connect() as con:
        rows = con.execute("SELECT key, value FROM settings").fetchall()
    settings = dict(config.DEFAULT_SETTINGS)
    settings.update({r["key"]: r["value"] for r in rows})
    return settings


def set_setting(key, value):
    with connect() as con:
        con.execute("INSERT INTO settings (key, value) VALUES (%s, %s) "
                    "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (key, Jsonb(value)))


# ---------------- users: administrators only (SR33; visitors have no account) ----------------
ROLES = ("admin", "user")       # user: a visitor who signed up to keep their history (SPEC 11, 2026-11-12)
LOGIN_FAILED = "Wrong email or password."     # the same message in every case: it does not say which emails exist
# a real bcrypt hash of a random text, used when the email is unknown, so that every login takes the same time
DUMMY_HASH = bcrypt.hashpw(b"no-such-user", bcrypt.gensalt()).decode()


def create_user(email, password, role="admin"):
    """Creates the account, or resets its password, role and 'active' if the email exists (FR12)."""
    if role not in ROLES:
        raise ValueError(f"unknown role: {role}")
    h = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    with connect() as con:
        con.execute("INSERT INTO users (email, password_hash, role) VALUES (%s, %s, %s) "
                    "ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash, "
                    "role = EXCLUDED.role, active = TRUE",
                    (email.lower().strip(), h, role))


def create_visitor(email, password):
    """Sign-up (SPEC 11, 2026-11-12): a NEW 'user' account, or None if the email is already used.
    Unlike create_user, it never changes an existing account (no password reset by signing up)."""
    h = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    with connect() as con:
        row = con.execute("INSERT INTO users (email, password_hash, role) VALUES (%s, %s, 'user') "
                          "ON CONFLICT (email) DO NOTHING RETURNING id", (email.lower().strip(), h)).fetchone()
    return row["id"] if row else None


def check_login(email, password):
    """Returns (user, message). Locks the account for 15 minutes after 5 failures (SR36).
    Every failure gives the same message (unknown email, wrong password, locked or disabled account)."""
    now = datetime.datetime.now(datetime.timezone.utc)
    with connect() as con:
        u = con.execute("SELECT * FROM users WHERE email = %s", (email.lower().strip(),)).fetchone()
        if not u or not u["active"]:
            bcrypt.checkpw(password.encode(), DUMMY_HASH.encode())      # same time as a real check
            return None, LOGIN_FAILED
        if u["locked_until"] and u["locked_until"] > now:
            return None, LOGIN_FAILED
        if bcrypt.checkpw(password.encode(), u["password_hash"].encode()):
            con.execute("UPDATE users SET failed_logins = 0, locked_until = NULL WHERE id = %s", (u["id"],))
            return {"id": u["id"], "email": u["email"], "role": u["role"]}, ""
        failed = u["failed_logins"] + 1
        if failed >= config.LOCK_AFTER_FAILED_LOGINS:
            con.execute("UPDATE users SET failed_logins = 0, locked_until = %s WHERE id = %s",
                        (now + datetime.timedelta(minutes=config.LOCK_MINUTES), u["id"]))
        else:
            con.execute("UPDATE users SET failed_logins = %s WHERE id = %s", (failed, u["id"]))
        return None, LOGIN_FAILED


def account_for_log(email):
    """After a failed login: the account of that email (id, email, role) and why it failed, for the logs only.
    The visitor still gets the same message for every failure (SR36). None for an unknown email."""
    now = datetime.datetime.now(datetime.timezone.utc)
    with connect() as con:
        u = con.execute("SELECT id, email, role, active, locked_until FROM users WHERE email = %s",
                        (email.lower().strip(),)).fetchone()
    if not u:
        return None
    reason = ("disabled" if not u["active"] else "locked" if u["locked_until"] and u["locked_until"] > now
              else "wrong password")
    return {"id": u["id"], "email": u["email"], "role": u["role"], "reason": reason}


def active_role(user_id):
    """The role of an active account ('admin'), or None if it does not exist or is disabled.
    Read from the database at every request, so a disabled account loses access at once (NFR8)."""
    with connect() as con:
        u = con.execute("SELECT active, role FROM users WHERE id = %s", (user_id,)).fetchone()
    return u["role"] if u and u["active"] else None


# ---------------- plans and questions per day (SPEC 11, 2026-11-14) ----------------
PLANS = ("free", "paid")
# midnight today in Beirut, as a time PostgreSQL can compare with created_at
BEIRUT_MIDNIGHT = "(date_trunc('day', now() AT TIME ZONE 'Asia/Beirut') AT TIME ZONE 'Asia/Beirut')"


def questions_today(user_id):
    """The account's real answers since midnight, Beirut time: greetings, ERRORs and saved demo answers do not count."""
    with connect() as con:
        return con.execute(f"""SELECT count(*) AS n FROM query_log WHERE user_id = %s
                               AND created_at >= {BEIRUT_MIDNIGHT} AND status NOT IN ('WELCOME', 'ERROR')
                               AND NOT coalesce((details -> 'shown' ->> 'demo')::boolean, FALSE)""",
                           (user_id,)).fetchone()["n"]


def user_plan(user_id):
    with connect() as con:
        row = con.execute("SELECT plan FROM users WHERE id = %s", (user_id,)).fetchone()
    return row["plan"] if row else None


def set_plan(user_id, plan):
    """Changes a 'user' account's plan. Returns (old plan, None), or (None, why): 'not found' or 'not a user'."""
    with connect() as con:
        row = con.execute("SELECT role, plan FROM users WHERE id = %s FOR UPDATE", (user_id,)).fetchone()
        if not row:
            return None, "not found"
        if row["role"] != "user":
            return None, "not a user"
        con.execute("UPDATE users SET plan = %s WHERE id = %s", (plan, user_id))
    return row["plan"], None


def user_is_active_admin(user_id):
    return active_role(user_id) == "admin"


# ---------------- query log ----------------
def log_query(r, user_id=None, shown=None, chat_id=None, turn=None):
    """Saves one question and its result (FR28, SR41). Returns the new row's id.
    user_id: the account that asked (empty for a visitor without an account; SPEC 11, 2026-11-12).
    shown: the answer exactly as it was shown on the page.
    chat_id, turn: the account's chat, and what a follow-up needs of this answer (pipeline.turn_of; SPEC 11, 2026-11-14)."""
    removed_citations = [p for s in r["removed"] for p in s["problems"] if "citation" in p or "case name" in p]
    details = {"removed": r["removed"],
               "passages": [(pid, p["chunk_id"], p["score"]) for pid, p in r["passages"]]}
    if shown is not None:
        details["shown"] = shown
    if turn is not None:
        details["turn"] = turn
    with connect() as con:
        row = con.execute("""INSERT INTO query_log (question, status, reason, support_score, top_score,
            n_sentences, n_removed, removed_citations, fabrications_caught, ms_search, ms_model,
            ms_total, details, user_id, chat_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                          (r["question"], r["status"], r["reason"], r["support_score"], r["top_score"],
                           len(r["shown_sentences"]), len(r["removed"]), Jsonb(removed_citations),
                           r["fabrications_caught"], r["ms_search"], r["ms_model"], r["ms_total"],
                           Jsonb(details), user_id, chat_id)).fetchone()
        if chat_id is not None:
            con.execute("UPDATE chats SET updated_at = now() WHERE id = %s", (chat_id,))
    return row["id"]


# ---------------- saved chats (Joe, SPEC 11, 2026-11-14) ----------------
def create_chat(user_id, first_question):
    """A new chat for this account, named after its first question (cut to 80 characters)."""
    title = " ".join(first_question.split())[:80]
    with connect() as con:
        return con.execute("INSERT INTO chats (user_id, title) VALUES (%s, %s) RETURNING id",
                           (user_id, title)).fetchone()["id"]


def own_chat(user_id, chat_id):
    """True only if this chat exists AND belongs to this account."""
    with connect() as con:
        return con.execute("SELECT 1 FROM chats WHERE id = %s AND user_id = %s", (chat_id, user_id)).fetchone() is not None


def chat_history(chat_id, limit=10):
    """The chat's earlier turns for a follow-up, oldest first: only answers that kept a turn (not a greeting or an
    ERROR), the last `limit` of them."""
    with connect() as con:
        rows = con.execute("SELECT details->'turn' AS turn FROM query_log WHERE chat_id = %s "
                           "AND details ? 'turn' ORDER BY id DESC LIMIT %s", (chat_id, limit)).fetchall()
    return [r["turn"] for r in reversed(rows)]


def list_chats(user_id):
    """The account's own chats, newest first, with their number of questions."""
    with connect() as con:
        return con.execute("""SELECT c.id, c.title, c.created_at, c.updated_at, count(q.id) AS questions
                              FROM chats c LEFT JOIN query_log q ON q.chat_id = c.id WHERE c.user_id = %s
                              GROUP BY c.id ORDER BY c.updated_at DESC, c.id DESC""", (user_id,)).fetchall()


def chat_turns(user_id, chat_id):
    """One of the account's own chats with every question and the answer as it was shown; None for someone else's."""
    with connect() as con:
        chat = con.execute("SELECT id, title, created_at, updated_at FROM chats WHERE id = %s AND user_id = %s",
                           (chat_id, user_id)).fetchone()
        if not chat:
            return None
        chat["turns"] = con.execute("SELECT id, question, status, created_at, details->'shown' AS shown "
                                    "FROM query_log WHERE chat_id = %s ORDER BY id", (chat_id,)).fetchall()
    return chat


def user_history(user_id, limit=50):
    """The questions ONE account asked, newest first (SPEC 11: a user sees only their own)."""
    with connect() as con:
        return con.execute("SELECT id, question, status, created_at FROM query_log WHERE user_id = %s "
                           "ORDER BY id DESC LIMIT %s", (user_id, limit)).fetchall()


def user_question(user_id, query_id):
    """One of the account's own questions with the answer as it was shown, or None (also for someone else's)."""
    with connect() as con:
        return con.execute("SELECT id, question, status, created_at, details->'shown' AS shown FROM query_log "
                           "WHERE id = %s AND user_id = %s", (query_id, user_id)).fetchone()


# ---------------- jobs (re-index / evaluation in the background) ----------------
def start_job(kind):
    with connect() as con:
        return con.execute("INSERT INTO jobs (kind, status, message) VALUES (%s, 'running', '') "
                           "RETURNING id", (kind,)).fetchone()["id"]


def end_job(job_id, status, message=""):
    with connect() as con:
        con.execute("UPDATE jobs SET status = %s, message = %s WHERE id = %s", (status, message, job_id))


def save_report(kind, report):
    with connect() as con:
        con.execute("INSERT INTO ingestion_reports (kind, report) VALUES (%s, %s)", (kind, Jsonb(report)))
    print(json.dumps(report, indent=1, default=str))
