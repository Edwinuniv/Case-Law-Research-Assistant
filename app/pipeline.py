"""The journey of one question: check input -> search -> gate -> model -> verify -> support score -> status."""
import time
from app import config, llm
from app.verify import verify, count_fabrications

ANSWERED, LOW_CONFIDENCE, NOT_SUPPORTED, ERROR = "ANSWERED", "LOW_CONFIDENCE", "NOT_SUPPORTED", "ERROR"


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


def answer(question, searcher, index, settings, skip_gate=False):
    """skip_gate=True is used by the evaluation: the model is always called, so any threshold
    can be tested later without calling the model again."""
    t0 = time.perf_counter()
    r = {"question": question.strip(), "status": None, "reason": "", "sentences": [], "removed": [],
         "passages": [], "top_score": 0.0, "support_score": 0.0, "fabrications_caught": 0,
         "retrieved_decisions": [], "model_said": None, "ms_search": 0, "ms_model": 0, "ms_total": 0}

    t = time.perf_counter()                                      # 1. SEARCH (+ optional reranker)
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
