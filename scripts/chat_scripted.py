"""A scripted chat through the real pipeline (v2), one message a minute (Groq: 8,000 tokens a minute): the same
messages before and after a change. Prints, for each message: status, kept and removed sentences, the cases of the
new passages (does the search stay in the case?), tokens. About 5,000 tokens a message.
Usage: python -m scripts.chat_scripted eval/chats/counterman_messages.txt > eval/chats/NAME.txt"""
import sys, time
from app import db, pipeline
from app.citations import CitationIndex
from app.search import Searcher
MESSAGES = [l for l in open(sys.argv[1]).read().splitlines() if l.strip()]
settings = dict(db.get_settings(), prompt_version="v2")
searcher, index = Searcher(), CitationIndex()
history = []
for i, q in enumerate(MESSAGES):
    if i:
        time.sleep(62)
    r = pipeline.answer(q, searcher, index, settings, history=history or None)
    p = dict(r["passages"])
    new = r.get("new_passages", list(p))
    print(f"\n=== [{i + 1}] {q}\n{r['status']} | {r['reason'][:100]} | support {r['support_score']:.2f} | tokens {r.get('tokens')}")
    print("  new passages:", "; ".join(f"{k} {p[k]['case_name'][:40]} ({p[k]['date_filed'][:4]}) {p[k]['opinion_label']}" for k in new) or "none")
    for s in r["shown_sentences"]:
        print("  KEPT", s["sources"], s["text"])
    for s in r["removed"]:
        print("  REMOVED", s["sources"], s.get("text"), "|", "; ".join(s["problems"])[:120])
    if (t := pipeline.turn_of(r)):
        history.append(t)
    sys.stdout.flush()
