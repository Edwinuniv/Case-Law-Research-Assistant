"""All settings in one place (SR6). Secret values come from the .env file."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.getenv("DATA_DIR", ROOT / "data"))
BULK = DATA / "bulk"       # files downloaded from CourtListener (deleted after filtering)
WORK = DATA / "work"       # our filtered files (small)
EVAL_DIR = ROOT / "eval"   # test questions (committed to git)

# ---- Corpus scope (SPEC.md section 2, requirements appendix A) ----
COURT = os.getenv("COURT", "scotus")
DATE_FROM = os.getenv("DATE_FROM", "2000-01-01")
DATE_TO = os.getenv("DATE_TO", "2024-12-31")
RELEASE = os.getenv("CL_RELEASE", "2024-12-31")   # change this to load a newer release (NFR13)
BULK_URL = "https://storage.courtlistener.com/bulk-data/"
BULK_FILES = {name: f"{name}-{RELEASE}.csv.bz2" for name in
              ["courts", "dockets", "opinion-clusters", "opinions", "citations", "citation-map"]}
LICENCE = "Public Domain Mark 1.0 (CourtListener bulk data, free of known copyright restrictions)"
CSV_ESCAPECHAR = os.getenv("CSV_ESCAPECHAR", "\\") or None   # how the bulk CSV escapes quotes

# ---- Database ----
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://verdicta:verdicta@localhost:5432/verdicta")

# ---- Language model (any OpenAI-compatible provider) ----
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
LLM_TIMEOUT_SECONDS = 30      # SR4
LLM_JSON_RETRIES = 1          # SR20: retry once if the reply is not valid JSON

# ---- Local models (downloaded automatically the first time) ----
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384
RERANK_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"

# ---- Website and security ----
QUESTION_MIN_CHARS, QUESTION_MAX_CHARS = 3, 1000          # SR3
SESSION_SECRET = os.getenv("SESSION_SECRET", "change-me-in-production")
HTTPS_ONLY = os.getenv("HTTPS_ONLY", "0") == "1"          # 1 only on the deployed site
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change-me")
LOCK_AFTER_FAILED_LOGINS, LOCK_MINUTES = 5, 15            # SR36
COVERAGE = f"U.S. Supreme Court opinions filed {DATE_FROM[:4]}–{DATE_TO[:4]} (CourtListener release {RELEASE})"
EXAMPLE_QUESTIONS = [
    "Did the Supreme Court overrule Chevron deference?",
    "What standard did the Court adopt for true threats under the First Amendment?",
    "When does the Seventh Amendment require a jury trial for civil penalties?",
]

# ---- Default thresholds and weights (admin can change them on the Settings page) ----
DEFAULT_SETTINGS = {
    "min_retrieval": 0.35,   # best passage similarity below this -> not supported, model not called
    "tau_abstain": 0.55,     # support score below this -> not supported   (SR27)
    "tau_confident": 0.70,   # support score below this -> low confidence  (SR27)
    "retrieve_k": 20,        # passages kept after hybrid search          (SR17)
    "top_k": 8,              # passages given to the model                 (SR18)
    "use_reranker": False,   # the week-10 improvement                     (SR18)
    "w_retrieval": 0.5,      # support score weights                       (SR26)
    "w_grounded": 0.4,
    "w_passages": 0.1,
    "chunk_max_words": 350,  # chunk size (SR16), changed by a re-index
}
