"""DEFENCE DEMO (guide p.82, minutes 7-9: "show a FABRICATED citation that was removed"). Run 2 has none to show:
the model cites passages (P1...P8) and our code writes the citations, so it never invented one. This demo shows
what happens when a model does lie. A real question goes through the real search; then, instead of calling the
model, we write the draft a lying model would write: one honest sentence with a real quote, and three sentences
with the same quote plus a lie (an invented citation, a real citation of a case we did not retrieve, an invented
case name). The REAL verifier, with the real citation table, decides what a visitor would see.
No model call, no Groq key needed.
Usage: python -m scripts.demo_fabricated ["question"]"""
import re
import sys
from app import db
from app.verify import verify, count_fabrications

QUESTION = "Does Title VII protect gay and transgender employees from being fired?"
OTHER_CASES = ["467 U.S. 837", "347 U.S. 483", "410 U.S. 113"]        # Chevron, Brown, Roe: real, other cases
INVENTED = ["599 U.S. 999", "598 U.S. 997", "597 U.S. 995"]


def honest_quote(text, words=10):
    """10 words of the passage with no digit and no case name: a quote the verifier must accept."""
    tokens = text.split()
    for i in range(len(tokens) - words + 1):
        window = " ".join(tokens[i:i + words])
        if not re.search(r"\d|\bv\.|[\[\]*]", window):
            return window
    return " ".join(tokens[:words])


def lying_draft(passages, real_other, invented):
    quote = honest_quote(passages["P1"]["text"])
    say = lambda text: {"text": text, "sources": ["P1"], "quote": quote}
    return {"sentences": [say(f"The opinion says: “{quote}”."),
                          say(f"This was confirmed in {invented}."),
                          say(f"The same rule was applied in {real_other}."),
                          say("It was first said in Zorblax v. Quimby.")]}


def check(draft, passages, index):
    return verify(draft, passages, index)


def pick(candidates, ok):
    return next(c for c in candidates if ok(c))


def main(argv):
    from scripts.reverify_run import pipeline_search
    question = " ".join(argv) or QUESTION
    s = db.get_settings()
    search, index = pipeline_search(s)
    chosen, found = search(question)
    passages = {f"P{i + 1}": p for i, p in enumerate(chosen)}
    retrieved = {p["decision_id"] for p in found}
    real_other = pick(OTHER_CASES, lambda c: index.clusters_for(c) and not
                      {index.decision_for_cluster(k) for k in index.clusters_for(c)} & retrieved)
    invented = pick(INVENTED, lambda c: not index.clusters_for(c))
    draft = lying_draft(passages, real_other, invented)

    print(f"Question: {question}\nP1: {passages['P1']['case_name']} ({passages['P1'].get('opinion_label') or ''})\n")
    print("The draft a lying model would write (all four sentences cite P1 with the same real quote):")
    for i, x in enumerate(draft["sentences"], 1):
        print(f"  {i}. {x['text']}")
    kept, removed = check(draft, passages, index)
    print("\nWhat the REAL verifier does:")
    for x in kept:
        print(f"  KEPT     {x['text']}")
    for x in removed:
        print(f"  REMOVED  {x['text']}\n           reason: {'; '.join(x['problems'])}")
    print(f"\nFabricated citations caught: {count_fabrications(removed)}"
          f"   ({invented} is in no citation table; {real_other} is real but not a case we retrieved)")
    print("What the visitor sees: only the KEPT sentence, with the citation our code renders for P1.")


if __name__ == "__main__":
    main(sys.argv[1:])
