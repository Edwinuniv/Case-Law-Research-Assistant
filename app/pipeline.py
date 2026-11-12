"""The journey of one question: check input -> search -> gate -> model -> verify -> support score -> status."""
import time
from app import config, llm
from app.citations import find_case_names
from app.verify import verify, count_fabrications

ANSWERED, LOW_CONFIDENCE, NOT_SUPPORTED, ERROR = "ANSWERED", "LOW_CONFIDENCE", "NOT_SUPPORTED", "ERROR"
WELCOME = "WELCOME"

# A greeting or "what can you do" gets a fixed welcome message instead of "not supported" (2026-11-12).
# The WHOLE message must be a greeting and/or one of these phrases: a legal question that starts with
# "Hello," is not a greeting. The text is ours, not the model's: no search, no model call, no legal statement.
GREETING_WORDS = {"hi", "hello", "hey", "hiya", "greetings", "there", "good", "morning", "afternoon", "evening"}
HELP_PHRASES = {"", "help", "what can you do", "what do you do", "who are you", "what are you", "what is this",
                "what is verdicta", "how does this work", "how does it work", "how do you work", "how do i use this",
                "thanks", "thank you"}


def is_greeting(question):
    words = "".join(c if c.isalpha() else " " for c in (question or "").lower()).split()
    if not words:
        return False
    while words and words[0] in GREETING_WORDS:
        words.pop(0)
    return " ".join(words) in HELP_PHRASES


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


def answer(question, searcher, index, settings, skip_gate=False):
    """skip_gate=True is used by the evaluation: the model is always called, so any threshold
    can be tested later without calling the model again."""
    t0 = time.perf_counter()
    r = {"question": question.strip(), "status": None, "reason": "", "sentences": [], "removed": [],
         "passages": [], "top_score": 0.0, "support_score": 0.0, "fabrications_caught": 0,
         "retrieved_decisions": [], "model_said": None, "ms_search": 0, "ms_model": 0, "ms_total": 0}

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
        draft = llm.ask_model(r["question"], passages)
    except llm.ModelError as e:
        r["ms_model"] = ms(t)
        return finish(r, ERROR, f"language model failed: {e}", t0)
    r["ms_model"] = ms(t)
    r["model_said"] = draft.get("status") if isinstance(draft, dict) else None
    if r["model_said"] != "SUPPORTED" or not draft.get("sentences"):
        return finish(r, NOT_SUPPORTED, "the model said the passages do not answer this", t0)

    kept, removed = verify(draft, passages, index)               # 4. VERIFY EVERY SENTENCE
    r["removed"], r["fabrications_caught"] = removed, count_fabrications(removed)
    r["sentences"] = kept
    r["support_score"] = support_score(kept, removed, passages, settings)     # 5. SCORE + DECIDE
    status = decide(r["support_score"], len(kept), settings)
    reason = {NOT_SUPPORTED: "support score below the abstention threshold" if kept
              else "every sentence failed verification",
              LOW_CONFIDENCE: "support score between the two thresholds", ANSWERED: ""}[status]
    return finish(r, status, reason, t0)


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
