"""A chat in the terminal, to try follow-up questions (answer v2) before the website sends the chat.
Each question gets the last turns of this chat (pipeline.turn_of); every sentence still goes through the verifier.
Prints what the page would show, the removed sentences, which passages were new, and the tokens of each call.
Commands: "new" starts another chat, "quit" (or Ctrl+D) stops. Uses the model: about 5,000 tokens a question.
Usage: python -m scripts.chat"""
from app import db, pipeline
from app.citations import CitationIndex
from app.search import Searcher

settings = dict(db.get_settings(), prompt_version="v2")   # follow-ups exist only in v2; the site setting is not changed
print("Loading the search index...")
searcher, index = Searcher(), CitationIndex()
history = []
print('Ask a question. "new" starts another chat, "quit" stops.\n')

while True:
    try:
        question = input(f"[turn {len(history) + 1}] > ").strip()
    except (EOFError, KeyboardInterrupt):
        break
    if question.lower() in ("quit", "exit"):
        break
    if question.lower() == "new":
        history = []
        print("New chat.\n")
        continue
    if (error := pipeline.check_input(question)):
        print(error)
        continue
    r = pipeline.answer(question, searcher, index, settings, history=history or None)
    passages = dict(r["passages"])
    print(f"\nSTATUS: {r['status']}   {r['reason']}")
    print(f"support {r['support_score']:.2f}   best passage {r['top_score']:.2f}   {r['ms_total'] / 1000:.1f} s"
          f"   tokens {r.get('tokens', {})}")
    if r.get("follow_up"):
        print(f"follow-up: {len(passages) - len(r['new_passages'])} passage(s) from the chat, "
              f"new: {', '.join(r['new_passages']) or 'none'}")
    for s in r["shown_sentences"]:
        print(f"- {s['text']}")
        for pid in s["sources"]:
            print(f"    [{pid}] {passages[pid]['case_name']} - {passages[pid]['opinion_label']}")
    for s in r["removed"]:
        print(f"  REMOVED: {s.get('text')}\n      because: {'; '.join(s['problems'])}")
    if (turn := pipeline.turn_of(r)):
        history.append(turn)
    print()
