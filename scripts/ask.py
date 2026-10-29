"""Ask one question from the terminal and see every step.
Usage: python -m scripts.ask "Did the Supreme Court overrule Chevron deference?" """
import sys
from app import db
from app.citations import CitationIndex
from app.pipeline import answer, check_input
from app.search import Searcher

question = " ".join(sys.argv[1:])
if (error := check_input(question)):
    sys.exit(error)
r = answer(question, Searcher(), CitationIndex(), db.get_settings())
print(f"\nSTATUS: {r['status']}   {r['reason']}")
print(f"support score {r['support_score']}   best passage {r['top_score']:.3f}   {r['ms_total']} ms\n")
passages = dict(r["passages"])
for s in r["shown_sentences"]:
    print(f"- {s['text']}  (groundedness {s['groundedness']})")
    for p in s["sources"]:
        print(f"    [{p}] {passages[p]['case_name']} - {passages[p]['opinion_label']}")
    print(f"    quote: \"{s['quote']}\"")
for s in r["removed"]:
    print(f"\nREMOVED: {s.get('text')}\n    because: {'; '.join(s['problems'])}")
print("\nPassages given to the model:")
for pid, p in r["passages"]:
    print(f"  {pid}  {p['score']:.3f}  {p['case_name']} - {p['opinion_label']} - {p['section']}")
