"""THE IMPORTANT PART: checking every sentence before a visitor can see it.

A sentence is kept only if ALL of these are true:
  1. It cites at least one passage, and only passages we really sent to the model (SR22, SR24).
  2. Its quote (5+ words) is found, word for word, in one of its cited passages.
  3. Every citation in it resolves to a real case (citation table) AND is either the case of a
     retrieved passage or written in its cited passage (SR23).
  4. Every case name in it ("X v. Y") is the case of a cited passage or appears in one.
  5. Every number and date in it appears in its cited passages (SR25).
Otherwise the sentence is removed and we record why (FR7)."""
import re
import unicodedata
from app.citations import find_citations, find_case_names, name_words, CITATION_LIKE

STOPWORDS = set("""the a an of to in and or for on by with that this is was were be been are as at from
it its which who whom whose not no but if than then so such court courts held holds said says
there their they them he she his her we our you your may must shall would could should""".split())
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def norm(text):
    """Make text comparable: same quote marks, dashes and spaces, lower case."""
    text = unicodedata.normalize("NFKC", text or "")
    for a, b in (("“", '"'), ("”", '"'), ("‘", "'"), ("’", "'"), ("–", "-"), ("—", "-")):
        text = text.replace(a, b)
    return re.sub(r"\s+", " ", text).strip().lower()


def numbers_in(text):
    return {n.replace(",", "").rstrip(".") for n in NUMBER.findall(text or "")}


def groundedness(sentence_text, cited_text):
    """Share of the sentence's meaningful words that appear in its cited passages (0..1)."""
    words = [w for w in re.findall(r"[a-z]{3,}", norm(sentence_text)) if w not in STOPWORDS]
    if not words:
        return 0.0
    vocabulary = set(re.findall(r"[a-z]{3,}", cited_text))
    return sum(w in vocabulary for w in words) / len(words)
