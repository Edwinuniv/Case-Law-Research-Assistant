"""Answers the example questions of the chat page once, with the real pipeline, and saves the answers
(app/demo.py). After this, asking one of them on the site costs no tokens and no waiting.
Run it again after a change to the prompt, the settings or the data. Uses the model: about 5,000 tokens a question.
Usage: python -m scripts.make_demo_answers"""
from app import db, demo
from app.citations import CitationIndex
from app.search import Searcher

db.init_db()
n = demo.make_all(Searcher(), CitationIndex())
print(f"\n{n} answer(s) saved.")
for row in demo.all_saved():
    print(f"  {row['saved_at']:%Y-%m-%d %H:%M}  {row['status']:15} {row['question']}")
