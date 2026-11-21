"""The journey of one question: check input -> search -> gate -> model -> verify -> support score -> status."""
import re
import time
from app import config, llm
from app.citations import find_case_names
from app.verify import verify, count_fabrications

ANSWERED, LOW_CONFIDENCE, NOT_SUPPORTED, ERROR = "ANSWERED", "LOW_CONFIDENCE", "NOT_SUPPORTED", "ERROR"
WELCOME = "WELCOME"

# A greeting or "what can you do" gets a fixed welcome message instead of "not supported" (2026-11-12).
# The WHOLE message must be a greeting and/or one of these phrases: a legal question that starts with
# "Hello," is not a greeting. The text is ours, not the model's: no search, no model call, no legal statement.
# "verdicta" too: people greet the assistant by its name ("hello verdicta" got "Not supported" live, 2026-11-15)
GREETING_WORDS = {"hi", "hello", "hey", "hiya", "greetings", "there", "good", "morning", "afternoon", "evening",
                  "verdicta"}
HELP_PHRASES = {"", "help", "what can you do", "what do you do", "who are you", "what are you", "what is this",
                "what is verdicta", "how does this work", "how does it work", "how do you work", "how do i use this",
                "thanks", "thank you"}


def squeeze(word):
    """A letter repeated in a row counts once: "hii", "heyyy", "hellooo" -> "hi", "hey", "helo" (2026-11-20)."""
    return "".join(c for i, c in enumerate(word) if i == 0 or c != word[i - 1])


SQUEEZED_GREETINGS = {squeeze(w) for w in GREETING_WORDS}


def is_greeting(question):
    words = "".join(c if c.isalpha() else " " for c in (question or "").lower()).split()
    if not words:
        return False
    while words and squeeze(words[0]) in SQUEEZED_GREETINGS:   # "hii" got "Not supported" live (2026-11-20)
        words.pop(0)
    return " ".join(words) in HELP_PHRASES


# In a chat (2026-11-13), "thanks" or "ok" gets one line instead of the whole welcome text. Also ours, no model call.
THANKS_WORDS = {"thanks", "thank", "you", "ok", "okay", "great", "got", "it", "cool", "perfect", "nice", "alright",
                "understood", "very", "much", "verdicta"}
THANKS_TEXT = "You're welcome. Ask another question about this case, or start a new chat for another one."


def is_thanks(question):
    words = "".join(c if c.isalpha() else " " for c in (question or "").lower()).split()
    return bool(words) and all(w in THANKS_WORDS for w in words)


OFF_TOPIC_TEXT = ("Verdicta is a case-law research assistant: it answers questions about U.S. Supreme Court decisions "
                  "from the text of the decisions, and it does not give opinions or answer questions outside the law.")


# Passage summaries (EVALUATION.md "Passage summaries", 2026-11-21): "summarize the first passage" is about the passages
# of the last answer. Live, it was searched alone and answered about another case. Now: those passages only, no search.
ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
            "1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5, "6th": 6, "7th": 7, "8th": 8, "last": "last"}
ORDINAL = r"\b(?:" + "|".join(ORDINALS) + r")\b"
JOINED = r"(?:\s*(?:,|and|&)\s*)?"
NO_PASSAGES_TEXT = ("I can summarise the passages of an answer in the same chat. Ask a question first, then for example "
                    "\"summarise the first passage\" or \"summarise all the passages\". To ask about a case, name it.")
PASSAGES_OFF_TEXT = ("The passages of the answer are under it: open \"Show the retrieved passages\" to read each one in "
                     "full. To ask about a case, name it in your question.")


SUMMARISE = re.compile(r"\bsu[mn]+[aeiou]?r[iy]?[sz]|\bsummary\b|\bsum\s+(?:it\s+)?up\b|\brecap\b|\bexplain|"
                       r"\btl;?dr\b|\bbreak\s+down\b|\bwhat\s+(?:does|did|do)\b.*\bsay")
OPINIONS = [("dissent", r"\bdissent(?:ing)?\b"), ("concurrence", r"\bconcurr(?:ence|ing)\b"),
            ("syllabus", r"\bsyllabus\b"), ("majority", r"\bmajority\b|\bopinion of the court\b|\bcourt'?s opinion\b")]


def speaker(p):
    """Who a passage is: the syllabus, a dissent, a concurrence or the majority (its label, as the verifier reads it)."""
    text = f"{p.get('opinion_label') or ''} {p.get('section') or ''}".lower()
    if p.get("is_syllabus") or "syllabus" in text:
        return "syllabus"
    return "dissent" if "dissent" in text else "concurrence" if "concurr" in text else "majority"


def cited_decision(previous, have):
    """The decision the last answer cited most (its shown sentences), else the decision of its first passage."""
    counts = {}
    for sentence in previous.get("sentences") or []:
        for pid in sentence.get("sources") or []:
            if pid in have:
                counts[have[pid]["decision_id"]] = counts.get(have[pid]["decision_id"], 0) + 1
    return max(counts, key=counts.get) if counts else have[min(have, key=lambda pid: int(pid[1:]))]["decision_id"]


def passage_request(question):
    """The passages a message asks about: ["P1", "P3"], ["last"] or ["all"]; None if it is not about the passages.
    "passage" must come with a number, an ordinal, "last" or "all" ("the passage of the Affordable Care Act" is a
    question about the law); a label "P2" counts alone. The verb does not matter ("summurize" was the live message)."""
    t = (question or "").lower()
    found = [f"P{n}" for n in re.findall(r"\bp\s?(\d{1,2})\b", t)]                          # "explain P3"
    for numbers in re.findall(r"\bpassages?\s+((?:\d{1,2}" + JOINED + r")+)", t):           # "passages 1 and 3"
        found += [f"P{n}" for n in re.findall(r"\d{1,2}", numbers)]
    for words in re.findall(r"((?:" + ORDINAL + JOINED + r")+)\s*passages?\b", t):          # "the second and third passages"
        found += [ORDINALS[w] if ORDINALS[w] == "last" else f"P{ORDINALS[w]}" for w in re.findall(ORDINAL, words)]
    if found:
        return sorted(set(found), key=lambda x: (x == "last", int(x[1:]) if x != "last" else 0))
    if re.search(r"\b(?:all|these|those|each|every|both|the)\s+(?:of\s+)?(?:the\s+)?passages\b(?!\s+of\b)", t) \
            or re.search(r"\b(?:each|every)\s+passage\b", t):
        return ["all"]
    # widened (2026-11-21): citations, opinions, the case - only with a summarising verb and no case named
    if not SUMMARISE.search(t) or find_case_names(question):
        return None
    cites = [f"C{n}" for n in re.findall(r"\bcitation\s+(\d)\b", t)]
    cites += [f"C{ORDINALS[w]}" for w in re.findall("(" + ORDINAL + r")\s+citation\b", t) if w != "last"]
    if cites:
        return sorted(set(cites))
    if re.search(r"\b(?:the|all|these|those|each|every)\s+(?:the\s+)?citations\b", t):
        return ["citations"]
    for kind, words in OPINIONS:
        if re.search(words, t):
            return [f"opinion:{kind}"]
    if re.search(r"\b(?:the|this|that)\s+(?:case|decision|opinion|ruling)\b|\bthe\s+cited\s+case\b", t):
        return ["case"]
    return None


def resolve_request(request, previous, have, labels, searcher, settings):
    """The passages a request means -> ({label: passage}, None), or ({}, our fixed text) when there is nothing to send.
    Passages and citations come from the last answer only. An opinion it did not have, and the case, are searched
    INSIDE the decision it cited (never another decision); new passages are labelled after its last label."""
    kind = request[0]
    if kind == "all":
        return {pid: have[pid] for pid in labels}, None
    if kind.startswith("P") or kind == "last":
        wanted = sorted({labels[-1] if x == "last" else x for x in request}, key=lambda pid: int(pid[1:]))
        if any(pid not in have for pid in wanted):
            return {}, (f"The last answer had {len(labels)} passages ({labels[0]}-{labels[-1]}). Ask about one of them, "
                        f"for example \"summarise {labels[0]}\".")
        return {pid: have[pid] for pid in wanted}, None
    cited = list(dict.fromkeys(pid for s in previous.get("sentences") or [] for pid in s.get("sources") or []
                               if pid in have))
    if kind.startswith("C") or kind == "citations":
        wanted = cited if kind == "citations" else [cited[int(x[1:]) - 1] for x in request if int(x[1:]) <= len(cited)]
        if not wanted or (kind != "citations" and len(wanted) < len(request)):
            return {}, (f"The last answer showed {len(cited)} citation{'s' if len(cited) != 1 else ''}. Ask about one "
                        f"of them, or about a passage (\"summarise P1\").")
        return {pid: have[pid] for pid in wanted}, None
    decision = cited_decision(previous, have)
    mine = {pid: p for pid, p in have.items() if p["decision_id"] == decision}
    want = kind.split(":")[1] if kind.startswith("opinion:") else None
    chosen = {pid: p for pid, p in mine.items() if want is None or speaker(p) == want}
    if want is None or not chosen:                     # the case, or an opinion the answer did not have: search inside
        query = f"{previous.get('question', '')} {want or ''}".strip()
        found = searcher.search(query, k=int(settings["retrieve_k"]), decision_ids=[decision])
        sent = {p["chunk_id"] for p in have.values()}
        new = [p for p in found if p["chunk_id"] not in sent and (want is None or speaker(p) == want)]
        if want is None:
            new.sort(key=lambda p: speaker(p) != "syllabus")          # the case: its syllabus first
        last = int(labels[-1][1:])
        chosen.update({f"P{last + i + 1}": p for i, p in enumerate(new[:4])})
    if not chosen:
        return {}, (f"The passages we have of {next(iter(mine.values()), {}).get('case_name', 'this case')} include no "
                    f"{want}. Ask about a passage of the answer (\"summarise P1\") or about another opinion.")
    return chosen, None


def answer_passages(question, request, previous, searcher, index, settings):
    """A passage request: the model gets ONLY the requested passages of the last answer (their labels kept), no search;
    every sentence goes through the same verifier against those passages, so citing another one fails check 1.
    Switched off, with no earlier answer, or a label the answer did not have: our fixed text (no model call)."""
    t0 = time.perf_counter()
    r = {"question": question.strip(), "status": None, "reason": "", "sentences": [], "removed": [], "passages": [],
         "top_score": 0.0, "support_score": 0.0, "fabrications_caught": 0, "retrieved_decisions": [], "model_said": None,
         "ms_search": 0, "ms_model": 0, "ms_total": 0, "off_topic": False, "passage_request": request}
    if not settings.get("passage_summaries", False):            # off until the measurement holds
        return finish(r, WELCOME, PASSAGES_OFF_TEXT, t0)
    have = dict((previous or {}).get("passages") or [])
    if not have:
        return finish(r, WELCOME, NO_PASSAGES_TEXT, t0)
    labels = sorted(have, key=lambda pid: int(pid[1:]))
    t = time.perf_counter()
    passages, missing = resolve_request(request, previous, have, labels, searcher, settings)
    r["ms_search"] = ms(t)
    if missing:
        return finish(r, WELCOME, missing, t0)
    r["passages"], r["retrieved_decisions"] = list(passages.items()), sorted({p["decision_id"] for p in passages.values()})
    r["top_score"] = max(p.get("score", 0.0) for p in passages.values())
    wanted = list(passages)
    asked = (f"{r['question']}\n(Summarise only passage{'s' if len(wanted) > 1 else ''} {', '.join(wanted)}: what "
             f"{'they say' if len(wanted) > 1 else 'it says'}, who is speaking (the Court, a concurrence, a dissent or the "
             f"syllabus, as the passage's label says) and why. A dissent or concurrence often states the majority's or a "
             f"party's view before answering it: say whose view each point is. Name each Justice; do not use a pronoun "
             f"for a Justice.)")
    t = time.perf_counter()
    try:
        version = settings.get("prompt_version", "v1")
        draft = llm.ask_model(asked, passages) if version == "v1" else \
            llm.ask_model(asked, passages, None, version, settings.get("reasoning_effort", "low"))
    except llm.ModelError as e:
        r["ms_model"] = ms(t)
        return finish(r, ERROR, f"language model failed: {e}", t0)
    return check_draft(r, draft, passages, index, settings, t, t0, judge=True)


def follow_up_passages(found, context, settings, last_label=None):
    """The passages a follow-up adds to the chat (EVALUATION.md, answer v2 rule): none already sent; at most
    followup_same_topic (4) when the search's best decision is already in the chat, otherwise up to
    followup_new_topic (8). Labelled after the chat's highest label (last_label), so a label is never reused."""
    sent = {p["chunk_id"] for p in context.values()}
    same_topic = bool(found) and found[0]["decision_id"] in {p["decision_id"] for p in context.values()}
    limit = int(settings.get("followup_same_topic", 4) if same_topic else settings.get("followup_new_topic", 8))
    new = [p for p in found if p["chunk_id"] not in sent][:limit]
    start = len(context) if last_label is None else last_label
    return {f"P{start + i + 1}": p for i, p in enumerate(new)}


def welcome_text():
    examples = " or ".join(f"“{q}”" for q in config.EXAMPLE_QUESTIONS[:2])
    return (f"I answer questions about {config.COVERAGE}, using only the text of the decisions. Every sentence I show "
            f"cites the passage it comes from, and every citation is checked before you see it. If the decisions do not "
            f"answer a question, I say so instead of guessing. Ask one question at a time, for example {examples}.")


def check_input(question):
    """SR3: refuse too short / too long questions without calling the model. Returns an error or None."""
    q = (question or "").strip()
    if len(q) < config.QUESTION_MIN_CHARS or len(q) > config.QUESTION_MAX_CHARS:
        return f"Please type a question between {config.QUESTION_MIN_CHARS} and {config.QUESTION_MAX_CHARS:,} characters."
    return None


def support_score(kept, removed, passages, settings):
    """SR26: retrieval strength + groundedness + number of passages cited,
    multiplied by the share of sentences that survived verification."""
    if not kept:
        return 0.0
    cited = {p for s in kept for p in s["sources"]}
    retrieval = max(passages[p]["score"] for p in cited)
    grounded = sum(s["groundedness"] for s in kept) / len(kept)
    many = min(1.0, len(cited) / 2)
    raw = settings["w_retrieval"] * retrieval + settings["w_grounded"] * grounded + settings["w_passages"] * many
    return round(raw * len(kept) / (len(kept) + len(removed)), 4)


def decide(support, n_kept, settings):
    """SR27: the status from the support score and the two thresholds."""
    if n_kept == 0 or support < settings["tau_abstain"]:
        return NOT_SUPPORTED
    return LOW_CONFIDENCE if support < settings["tau_confident"] else ANSWERED


def named_decisions(question, index):
    """Metadata (2026-11-06, the instructor: "use metadata for faster search"): the decisions of our
    corpus named in the question, e.g. "... in Loper Bright Enterprises v. Raimondo". The search can then
    look only at their passages. Invented or mixed names match no decision, so the normal search runs.
    Off unless the setting case_filter is on (EVALUATION.md: switched on only after the measurement)."""
    return sorted({d for name in find_case_names(question) for d in index.decisions_named(name)})


def answer(question, searcher, index, settings, skip_gate=False, history=None, previous=None):
    """skip_gate=True is used by the evaluation: the model is always called, so any threshold
    can be tested later without calling the model again.
    history (answer v2, a follow-up): the earlier turns of the chat, oldest first, each {question, passages,
    sentences (verified only)}. With no history, everything below runs exactly as in the evaluated system.
    previous: the chat's last answer (a turn), for a passage request ("summarize the first passage")."""
    request = passage_request(question)
    if request is not None and (settings.get("passage_summaries", False) or not history):   # no eval-v1 question
        # is a request (test); off, a follow-up keeps it in the chat's case instead (EVALUATION.md, 2026-11-21)
        return answer_passages(question, request, previous or (history[-1] if history else None), searcher, index,
                               settings)
    if history:
        return answer_follow_up(question, searcher, index, settings, history)
    t0 = time.perf_counter()
    r = {"question": question.strip(), "status": None, "reason": "", "sentences": [], "removed": [],
         "passages": [], "top_score": 0.0, "support_score": 0.0, "fabrications_caught": 0,
         "retrieved_decisions": [], "model_said": None, "ms_search": 0, "ms_model": 0, "ms_total": 0,
         "off_topic": False}

    if is_greeting(r["question"]):                               # 0. A GREETING: our welcome text, nothing else
        return finish(r, WELCOME, welcome_text(), t0)

    t = time.perf_counter()                                      # 1. SEARCH (+ optional reranker)
    r["case_filter"] = named_decisions(r["question"], index) if settings.get("case_filter") else []
    if r["case_filter"]:                                         # only the named case's passages
        found = searcher.search(r["question"], k=int(settings["retrieve_k"]), decision_ids=r["case_filter"])
    else:
        found = searcher.search(r["question"], k=int(settings["retrieve_k"]))
    chosen = searcher.choose(r["question"], found, int(settings["top_k"]), settings["use_reranker"])
    r["ms_search"] = ms(t)
    r["retrieved_decisions"] = [p["decision_id"] for p in found]
    passages = {f"P{i + 1}": p for i, p in enumerate(chosen)}
    r["passages"] = list(passages.items())
    r["top_score"] = max((p["score"] for p in chosen), default=0.0)

    if not skip_gate and r["top_score"] < settings["min_retrieval"]:      # 2. CHEAP GATE
        return finish(r, NOT_SUPPORTED, "no passage is close enough to the question", t0)

    t = time.perf_counter()                                      # 3. ASK THE MODEL
    try:
        version = settings.get("prompt_version", "v1")
        draft = llm.ask_model(r["question"], passages) if version == "v1" else \
            llm.ask_model(r["question"], passages, None, version, settings.get("reasoning_effort", "low"))
    except llm.ModelError as e:
        r["ms_model"] = ms(t)
        return finish(r, ERROR, f"language model failed: {e}", t0)
    return check_draft(r, draft, passages, index, settings, t, t0)


NOT_SUPPORTED_BY_JUDGE = "the judge says the cited passage does not support it"


def judged(kept, removed, passages):
    """The meaning check of a summary (EVALUATION.md, 2026-11-21): only sentences the judge fully supports ("yes") stay;
    "partly", "no" or a failed judge removes the sentence (fails closed)."""
    still = []
    for sentence in kept:
        try:
            verdict = llm.judge_summary(sentence["text"], " ".join(passages[p]["text"] for p in sentence["sources"]))
        except llm.ModelError:
            verdict = "error"
        (still if verdict == "yes" else removed).append(
            sentence if verdict == "yes" else {**sentence, "problems": [NOT_SUPPORTED_BY_JUDGE]})
    return still, removed


def check_draft(r, draft, passages, index, settings, t, t0, judge=False):
    """Steps 4 and 5, the same for a first question and a follow-up: verify every sentence, score, decide.
    judge=True (passage summaries only): the meaning check after the six checks."""
    r["ms_model"] = ms(t)
    r["tokens"] = dict(llm.LAST_USAGE)                            # input, cached, output (answer v2 rule: measured)
    r["model_said"] = draft.get("status") if isinstance(draft, dict) else None
    if r["model_said"] == "OFF_TOPIC":                           # not about the law: our fixed message, an abstention
        r["off_topic"] = True
        return finish(r, NOT_SUPPORTED, OFF_TOPIC_TEXT, t0)
    if r["model_said"] != "SUPPORTED" or not draft.get("sentences"):
        return finish(r, NOT_SUPPORTED, "the model said the passages do not answer this", t0)

    kept, removed = verify(draft, passages, index)               # 4. VERIFY EVERY SENTENCE
    if judge:                                                     # 4b. summaries: does it MEAN what the passage says
        kept, removed = judged(kept, removed, passages)
    r["removed"], r["fabrications_caught"] = removed, count_fabrications(removed)
    r["sentences"] = kept
    r["support_score"] = support_score(kept, removed, passages, settings)     # 5. SCORE + DECIDE
    status = decide(r["support_score"], len(kept), settings)
    reason = {NOT_SUPPORTED: "support score below the abstention threshold" if kept
              else "every sentence failed verification",
              LOW_CONFIDENCE: "support score between the two thresholds", ANSWERED: ""}[status]
    return finish(r, status, reason, t0)


def answer_follow_up(question, searcher, index, settings, history):
    """A follow-up (answer v2): the model reads the last turns of the chat; the search runs on the earlier question and
    the new one together; only the passages the chat does not have yet are added (follow_up_passages). Every sentence
    is verified against ALL the passages of the chat, which are the passages the model received."""
    t0 = time.perf_counter()
    history = history[-int(settings.get("followup_max_turns", 4)):]
    r = {"question": question.strip(), "status": None, "reason": "", "sentences": [], "removed": [], "passages": [],
         "top_score": 0.0, "support_score": 0.0, "fabrications_caught": 0, "retrieved_decisions": [], "model_said": None,
         "ms_search": 0, "ms_model": 0, "ms_total": 0, "follow_up": True, "off_topic": False}
    if is_thanks(r["question"]):                                 # "thanks", "ok": one line, not the welcome text
        return finish(r, WELCOME, THANKS_TEXT, t0)
    if is_greeting(r["question"]):
        return finish(r, WELCOME, welcome_text(), t0)
    context = {pid: p for turn in history for pid, p in llm.cited_passages(turn).items()}   # what is sent (part 3)
    last_label = max((int(pid[1:]) for turn in history for pid, _ in turn["passages"]), default=0)
    t = time.perf_counter()
    query = f"{history[-1]['question']} {r['question']}"         # "and the dissent?" needs the earlier question
    found = chat_case_search(r["question"], query, history, searcher, index, settings)
    chosen = searcher.choose(query, found, int(settings["top_k"]), settings["use_reranker"])
    new = follow_up_passages(chosen, context, settings, last_label)
    version = settings.get("prompt_version", "v2")
    budget = int(settings.get("followup_max_input_tokens", 6000))     # Groq free tier: 8,000 a minute (part 3)
    while history and llm.estimate_tokens(llm.build_messages(r["question"], new, history, version)) > budget:
        history = history[1:]                                     # the oldest turn is forgotten first
    context = {pid: p for turn in history for pid, p in llm.cited_passages(turn).items()}
    r["ms_search"] = ms(t)
    r["retrieved_decisions"] = [p["decision_id"] for p in found]
    passages = {**context, **new}
    r["passages"], r["new_passages"] = list(passages.items()), list(new)
    r["top_score"] = max((p["score"] for p in passages.values()), default=0.0)
    t = time.perf_counter()
    try:
        draft = llm.ask_model(r["question"], new, history, version, settings.get("reasoning_effort", "low"))
    except llm.ModelError as e:
        r["ms_model"] = ms(t)
        return finish(r, ERROR, f"language model failed: {e}", t0)
    return check_draft(r, draft, passages, index, settings, t, t0)


def turn_of(r):
    """What a chat keeps of an answer for the next follow-up: the question, every passage the model had, and only
    the sentences shown (none when NOT_SUPPORTED), so a removed sentence is never sent back to the model.
    A greeting or an error is not a turn (None): nothing was searched or answered."""
    if r["status"] in (WELCOME, ERROR) or r.get("passage_request"):   # a summary is not a turn: "now passage 2"
        return None                                                    # still means the same answer
    return {"question": r["question"], "passages": r["passages"], "sentences": r["shown_sentences"]}


def chat_case_search(question, query, history, searcher, index, settings):
    """The search of a follow-up stays in the case the chat is about ("what did the victim do?"): the decisions cited
    by the chat's shown sentences. A case named in the new message is searched instead. With no cited decision, or no
    passage of them reaching min_retrieval, the whole corpus is searched, as before (EVALUATION.md, 2026-11-13)."""
    k = int(settings["retrieve_k"])
    cited = sorted({dict(turn["passages"])[pid]["decision_id"] for turn in history
                    for s in turn["sentences"] for pid in s["sources"] if pid in dict(turn["passages"])})
    decisions = named_decisions(question, index) or cited
    if decisions:
        found = searcher.search(query, k=k, decision_ids=decisions)
        if found and max(p["score"] for p in found) >= settings["min_retrieval"]:
            return found
    return searcher.search(query, k=k)


def finish(r, status, reason, t0):
    r["status"], r["reason"] = status, reason
    if status in (NOT_SUPPORTED, ERROR):
        r["shown_sentences"] = []                    # SR28: no generated text when not supported
    else:
        r["shown_sentences"] = r["sentences"]
    r["ms_total"] = ms(t0)
    return r


def ms(t):
    return int((time.perf_counter() - t) * 1000)
