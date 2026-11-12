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
    role TEXT NOT NULL DEFAULT 'admin' CHECK (role IN ('admin')),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    failed_logins INT NOT NULL DEFAULT 0,
    locked_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now());

CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value JSONB NOT NULL);

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
"""

INDEXES = """
CREATE INDEX IF NOT EXISTS citations_lookup ON citations (reporter, volume, page);
CREATE INDEX IF NOT EXISTS citation_map_citing ON citation_map (citing_opinion_id);
CREATE INDEX IF NOT EXISTS chunks_decision ON chunks (decision_id);
CREATE INDEX IF NOT EXISTS query_log_time ON query_log (created_at);
"""

# Changes to tables that already exist (CREATE TABLE IF NOT EXISTS does not change them).
# Safe to run at every start.
MIGRATIONS = """
-- 2026-11-06 (step 5.7): who asked each question (FR28 already saves the question)
ALTER TABLE query_log ADD COLUMN IF NOT EXISTS user_id INT REFERENCES users(id);
CREATE INDEX IF NOT EXISTS query_log_user ON query_log (user_id, id);
-- 2026-11-06 (step 5.11): the instructor's answer, only the administrator logs in (SR33 as written).
-- Steps 5.6-5.10 had a 'user' role: those accounts are removed (their questions stay in the log,
-- without the account), then the rule allows 'admin' only. Does nothing on a database without them.
UPDATE query_log SET user_id = NULL WHERE user_id IN (SELECT id FROM users WHERE role <> 'admin');
DELETE FROM users WHERE role <> 'admin';
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users ADD CONSTRAINT users_role_check CHECK (role IN ('admin'));
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
ROLES = ("admin",)
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


def active_role(user_id):
    """The role of an active account ('admin'), or None if it does not exist or is disabled.
    Read from the database at every request, so a disabled account loses access at once (NFR8)."""
    with connect() as con:
        u = con.execute("SELECT active, role FROM users WHERE id = %s", (user_id,)).fetchone()
    return u["role"] if u and u["active"] else None


def user_is_active_admin(user_id):
    return active_role(user_id) == "admin"


# ---------------- query log ----------------
def log_query(r, user_id=None, shown=None):
    """Saves one question and its result (FR28, SR41). Returns the new row's id.
    user_id: the account that asked (empty for visitors, who have no account; step 5.11).
    shown: the answer exactly as it was shown on the page."""
    removed_citations = [p for s in r["removed"] for p in s["problems"] if "citation" in p or "case name" in p]
    details = {"removed": r["removed"],
               "passages": [(pid, p["chunk_id"], p["score"]) for pid, p in r["passages"]]}
    if shown is not None:
        details["shown"] = shown
    with connect() as con:
        row = con.execute("""INSERT INTO query_log (question, status, reason, support_score, top_score,
            n_sentences, n_removed, removed_citations, fabrications_caught, ms_search, ms_model,
            ms_total, details, user_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                          (r["question"], r["status"], r["reason"], r["support_score"], r["top_score"],
                           len(r["shown_sentences"]), len(r["removed"]), Jsonb(removed_citations),
                           r["fabrications_caught"], r["ms_search"], r["ms_model"], r["ms_total"],
                           Jsonb(details), user_id)).fetchone()
    return row["id"]


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
