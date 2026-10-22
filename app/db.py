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
"""

INDEXES = """
CREATE INDEX IF NOT EXISTS citations_lookup ON citations (reporter, volume, page);
CREATE INDEX IF NOT EXISTS citation_map_citing ON citation_map (citing_opinion_id);
CREATE INDEX IF NOT EXISTS chunks_decision ON chunks (decision_id);
CREATE INDEX IF NOT EXISTS query_log_time ON query_log (created_at);
"""


def connect():
    """Use as: with db.connect() as con: ...  (commits automatically at the end)."""
    return psycopg.connect(config.DATABASE_URL, row_factory=dict_row)


def init_db():
    with connect() as con:
        con.execute(SCHEMA)
        con.execute(INDEXES)
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


# ---------------- users (administrators) ----------------
def create_user(email, password):
    h = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    with connect() as con:
        con.execute("INSERT INTO users (email, password_hash) VALUES (%s, %s) "
                    "ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash, active = TRUE",
                    (email.lower().strip(), h))


def check_login(email, password):
    """Returns (user, message). Locks the account for 15 minutes after 5 failures (SR36)."""
    now = datetime.datetime.now(datetime.timezone.utc)
    with connect() as con:
        u = con.execute("SELECT * FROM users WHERE email = %s", (email.lower().strip(),)).fetchone()
        if not u or not u["active"]:
            return None, "Wrong email or password."
        if u["locked_until"] and u["locked_until"] > now:
            return None, "Too many failed attempts. This account is locked for 15 minutes."
        if bcrypt.checkpw(password.encode(), u["password_hash"].encode()):
            con.execute("UPDATE users SET failed_logins = 0, locked_until = NULL WHERE id = %s", (u["id"],))
            return {"id": u["id"], "email": u["email"], "role": u["role"]}, ""
        failed = u["failed_logins"] + 1
        if failed >= config.LOCK_AFTER_FAILED_LOGINS:
            con.execute("UPDATE users SET failed_logins = 0, locked_until = %s WHERE id = %s",
                        (now + datetime.timedelta(minutes=config.LOCK_MINUTES), u["id"]))
            return None, "Too many failed attempts. This account is locked for 15 minutes."
        con.execute("UPDATE users SET failed_logins = %s WHERE id = %s", (failed, u["id"]))
        return None, "Wrong email or password."


def user_is_active_admin(user_id):
    with connect() as con:
        u = con.execute("SELECT active, role FROM users WHERE id = %s", (user_id,)).fetchone()
    return bool(u and u["active"] and u["role"] == "admin")


# ---------------- query log ----------------
def log_query(r):
    removed_citations = [p for s in r["removed"] for p in s["problems"] if "citation" in p or "case name" in p]
    details = {"removed": r["removed"],
               "passages": [(pid, p["chunk_id"], p["score"]) for pid, p in r["passages"]]}
    with connect() as con:
        con.execute("""INSERT INTO query_log (question, status, reason, support_score, top_score,
            n_sentences, n_removed, removed_citations, fabrications_caught, ms_search, ms_model,
            ms_total, details) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (r["question"], r["status"], r["reason"], r["support_score"], r["top_score"],
                     len(r["shown_sentences"]), len(r["removed"]), Jsonb(removed_citations),
                     r["fabrications_caught"], r["ms_search"], r["ms_model"], r["ms_total"],
                     Jsonb(details)))


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
