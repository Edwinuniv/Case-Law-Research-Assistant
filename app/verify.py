"""THE IMPORTANT PART: checking every sentence before a visitor can see it.

A sentence is kept only if ALL of these are true:
  1. It cites at least one passage, and only passages we really sent to the model (SR22, SR24).
  2. Its quote (5+ words) is found, word for word, in one of its cited passages.
  3. Every citation in it resolves to a real case (citation table) AND is either the case of a
     retrieved passage or written in its cited passage (SR23).
  4. Every case name in it ("X v. Y") is the case of a cited passage or appears in one.
  5. Every number and date in it appears in its cited passages (SR25).
  6. It does not present a dissent or concurrence as the Court's view (added in Week 7).
Otherwise the sentence is removed and we record why (FR7)."""
import re
import unicodedata
from app.citations import find_citations, find_case_names, name_key, CITATION_LIKE

STOPWORDS = set("""the a an of to in and or for on by with that this is was were be been are as at from
it its which who whom whose not no but if than then so such court courts held holds said says
there their they them he she his her we our you your may must shall would could should""".split())
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
# Numbers written as words, "two" to "ninety-nine" (Week 7: "five to four" got through check 5).
# "one" is left out on purpose: it is usually a pronoun ("no one can miss").
UNITS = dict(zip("two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
                 "seventeen eighteen nineteen".split(), range(2, 20)))
TENS = dict(zip("twenty thirty forty fifty sixty seventy eighty ninety".split(), range(20, 100, 10)))
DIGIT_WORDS = dict(UNITS, one=1)
NUMBER_WORD = re.compile(rf"\b(?:({'|'.join(TENS)})(?:[- ]({'|'.join(DIGIT_WORDS)}))?|({'|'.join(UNITS)}))\b", re.I)
# Passage markers the model writes inside the text, like ["P1"] or [P1, P3]. Not in the guide:
# check 5 read the 1 in "P1" as a number and removed correct sentences (see AI_LOG.md).
PASSAGE_MARK = re.compile(r"\s*\[\s*\"?P\d+\"?(?:\s*,\s*\"?P\d+\"?)*\s*\]")
# Check 6 (Week 7): who is speaking. A passage is a separate opinion if its label or section says so
# ("Dissenting opinion (Kagan)", "Gorsuch, J., concurring"); a sentence speaks for the Court unless it
# names the separate opinion itself ("the dissent argued", "Justice Gorsuch, concurring").
SEPARATE_OPINION = re.compile(r"dissent|concurr", re.I)
COURT_VIEW = re.compile(r"\b(?:the (?:supreme )?court|the majority)\b", re.I)
NAMES_SEPARATE_OPINION = re.compile(r"\b(?:dissent\w*|concurr\w*|justice \w+|\w+, j\.)", re.I)


def separate_opinion(passage):
    return bool(SEPARATE_OPINION.search(f"{passage.get('opinion_label') or ''} {passage.get('section') or ''}"))


def norm(text):
    """Make text comparable: same quote marks, dashes and spaces, lower case."""
    text = unicodedata.normalize("NFKC", text or "")
    for a, b in (("“", '"'), ("”", '"'), ("‘", "'"), ("’", "'"), ("–", "-"), ("—", "-")):
        text = text.replace(a, b)
    return re.sub(r"\s+", " ", text).strip().lower()


def numbers_in(text):
    return {n.replace(",", "").rstrip(".") for n in NUMBER.findall(text or "")}


def number_words_in(text):
    """'six to three' -> {'6', '3'}; 'twenty-five' -> {'25'}."""
    found = set()
    for tens, unit, small in NUMBER_WORD.findall(text or ""):
        value = TENS[tens.lower()] + DIGIT_WORDS[unit.lower()] if tens and unit else \
            TENS[tens.lower()] if tens else UNITS[small.lower()]
        found.add(str(value))
    return found


def groundedness(sentence_text, cited_text):
    """Share of the sentence's meaningful words that appear in its cited passages (0..1)."""
    words = [w for w in re.findall(r"[a-z]{3,}", norm(sentence_text)) if w not in STOPWORDS]
    if not words:
        return 0.0
    vocabulary = set(re.findall(r"[a-z]{3,}", cited_text))
    return sum(w in vocabulary for w in words) / len(words)


def check_sentence(sentence, passages, index):
    text, sources, quote = sentence.get("text") or "", sentence.get("sources") or [], sentence.get("quote") or ""
    problems = []
    cited = [passages[p] for p in sources if p in passages]
    if not sources or len(cited) != len(sources):                                 # check 1
        return ["cites a passage that was not sent to the model"]
    cited_text = norm(" ".join(c["text"] for c in cited))
    if len(quote.split()) < 5 or norm(quote) not in cited_text:                   # check 2
        problems.append("quote not found in the cited passage")

    retrieved_decisions = {p["decision_id"] for p in passages.values()}
    passage_cites = set().union(*(find_citations(c["text"]) for c in cited))
    for cite in find_citations(text):                                              # check 3
        cluster = index.cluster_for(cite)
        if cluster is None:
            problems.append(f"FABRICATED citation (not in the citation table): {cite}")
        elif index.decision_for_cluster(cluster) in retrieved_decisions:
            continue
        elif cite in passage_cites or norm(cite) in cited_text:
            continue
        else:
            problems.append(f"real citation not supported by the retrieved opinions: {cite}")

    cited_names = [name_key(c["case_name"]) for c in cited]
    for name in find_case_names(text):                                             # check 4
        if name_key(name) in cited_names or norm(name) in cited_text:
            continue
        kind = "case name not supported by the cited passage" if index.known_case_name(name) \
            else "FABRICATED case name"
        problems.append(f"{kind}: {name}")

    text_without_citations = CITATION_LIKE.sub(" ", text)                         # check 5
    passage_numbers = numbers_in(cited_text) | number_words_in(cited_text)
    sentence_numbers = numbers_in(text_without_citations) | number_words_in(text_without_citations)
    for number in sorted(sentence_numbers - passage_numbers):
        problems.append(f"number or date not in the cited passage: {number}")

    if COURT_VIEW.search(text) and not NAMES_SEPARATE_OPINION.search(text) \
            and all(separate_opinion(c) for c in cited):                          # check 6
        problems.append("dissent or concurrence presented as the Court's view")
    return problems


def verify(draft, passages, index):
    """Returns (kept, removed). Each kept sentence gets its groundedness; removed ones their problems."""
    kept, removed = [], []
    for s in draft.get("sentences") or []:
        if not isinstance(s, dict):
            removed.append({"text": str(s), "sources": [], "problems": ["not a valid sentence"]})
            continue
        s = {**s, "text": PASSAGE_MARK.sub("", s.get("text") or "")}
        problems = check_sentence(s, passages, index)
        if problems:
            removed.append({**s, "problems": problems})
        else:
            cited_text = norm(" ".join(passages[p]["text"] for p in s["sources"]))
            kept.append({**s, "groundedness": round(groundedness(s["text"], cited_text), 3), "problems": []})
    return kept, removed


def count_fabrications(removed):
    return sum(1 for s in removed for p in s["problems"] if p.startswith("FABRICATED"))
