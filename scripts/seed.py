"""SR5 - ONE script that prepares a database (local or on the server):
tables, corpus, citation table + citation map, search index, test questions, admin account.

Usage:
  python -m scripts.seed --all                      # everything
  python -m scripts.seed --schema --corpus          # only some parts
Parts: --schema --corpus --citations --index --questions --admin
The DATABASE_URL in .env (or in the environment) decides which database is filled."""
import sys
from app import config, db, ingest

parts = {a.lstrip("-") for a in sys.argv[1:]}
if "all" in parts:
    parts = {"schema", "corpus", "citations", "index", "questions", "admin"}
if not parts:
    sys.exit(__doc__)

print(f"Database: {config.DATABASE_URL.split('@')[-1]}")
db.init_db()                                              # always safe: creates what is missing
if "corpus" in parts:
    print("Loading decisions and opinions...")
    ingest.load_corpus()
if "citations" in parts:
    print("Loading the citation table and the citation map...")
    ingest.load_citations()
if "index" in parts:
    print("Building the search index (chunks + embeddings)...")
    from app import indexing          # imported here: this file only exists from week 2
    indexing.build_index(max_words=int(db.get_settings().get("chunk_max_words", 350)))
if "questions" in parts:
    from app import evaluate          # imported here: this file only exists from week 5
    print(f"Imported {evaluate.import_questions()} test questions from eval/questions.jsonl")
if "admin" in parts:
    db.create_user(config.ADMIN_EMAIL, config.ADMIN_PASSWORD)
    print(f"Admin account ready: {config.ADMIN_EMAIL}")
print("Seed finished.")
