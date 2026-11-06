"""Putting back the letters lost with the PDF ligatures "fi" and "fl".

Some opinions were extracted from PDFs where the single glyph for "fi" or "fl" became a plain "f":
"first" -> "frst", "affirm" -> "affrm", "specific" -> "specifc", "conflict" -> "confict" (Edwin, 2026-11-06:
1,865 passages in 123 decisions). The repair is deliberately narrow:
- the only change is inserting "i" or "l" right after an "f" (that is exactly what the ligature lost);
- the repaired word must be COMMON in the corpus (at least MIN_GOOD times) and far more common than the
  broken word (RATIO times), so a real word such as "lies" or "fed" is never changed;
- only broken opinions are touched: at least MIN_HITS repairable words, and more of them than intact
  fi/fl words (is_broken), so a clean opinion stays exactly as it is, even one that says "fled" often;
- a broken form that is also a real word ("fled", "rife", "Fred": used in clearly clean opinions) is
  repaired only inside a broken PDF, and only if a broken PDF could not have printed it intact
  ("fled" has an 'fl', so there it can only be "filed"; "rife" stays); partly broken opinions get only
  the forms that are never real words ("specifc") (real_words, fix_opinion).
The corpus itself is the dictionary: the 3,500 clean opinions spell the words correctly."""
import re
from collections import Counter

MIN_GOOD, RATIO, MIN_HITS, MIN_LEN = 20, 10, 3, 3
MAX_CLEAN, CLEAN_RATIO = 2, 10      # see real_words
WORD = re.compile(r"[A-Za-z]+")


def vocabulary(texts):
    """How often each lower-case word appears in all the texts."""
    counts = Counter()
    for text in texts:
        counts.update(w.lower() for w in WORD.findall(text))
    return counts


def candidates(word):
    """Every word made by inserting 'i' or 'l' right after one of the f's of `word`."""
    return {word[:i + 1] + extra + word[i + 1:] for i, ch in enumerate(word) if ch == "f" for extra in "il"}


def repairs(vocab):
    """broken word -> repaired word, for the words that pass the rules above."""
    found = {}
    for word, n in vocab.items():
        if len(word) < MIN_LEN or "f" not in word:
            continue
        best = max(candidates(word), key=lambda c: vocab.get(c, 0))
        if vocab.get(best, 0) >= MIN_GOOD and vocab[best] >= RATIO * n:
            found[word] = best
    return found


def can_be_printed_intact(word):
    """A broken PDF lost every 'fi' and 'fl', so a word that still contains one cannot come from it intact."""
    return "fi" not in word and "fl" not in word


def counts(text, mapping):
    """(repairable words, intact fi/fl words) in one text."""
    words = [w.lower() for w in WORD.findall(text)]
    return (sum(1 for w in words if w in mapping),
            sum(1 for w in words if ("fi" in w or "fl" in w) and w not in mapping))


def real_words(mapping, texts):
    """The broken forms that are also real words ('fled', 'rife', 'Fred'): used more than MAX_CLEAN times
    in the CLEARLY clean opinions (at least CLEAN_RATIO intact fi/fl words per repairable word). Partly
    broken opinions are left out of this count, otherwise their 'specifc' would look like a real word."""
    clean = Counter()
    for text in texts:
        hits, intact = counts(text, mapping)
        if intact >= CLEAN_RATIO * max(hits, 1):
            clean.update(w.lower() for w in WORD.findall(text) if w.lower() in mapping)
    return {w for w in mapping if clean[w] > MAX_CLEAN}


def same_case(original, repaired):
    """'Frst' -> 'First', 'FRST' -> 'FIRST', 'frst' -> 'first'."""
    if original.isupper() and len(original) > 1:
        return repaired.upper()
    if original[0].isupper():
        return repaired[0].upper() + repaired[1:]
    return repaired


def fix_text(text, mapping):
    """The text with every broken word repaired, and the number of words changed."""
    hits = 0

    def swap(m):
        nonlocal hits
        fixed = mapping.get(m.group(0).lower())
        if fixed is None:
            return m.group(0)
        hits += 1
        return same_case(m.group(0), fixed)
    return WORD.sub(swap, text), hits


def is_broken(text, mapping):
    """A broken PDF has (almost) no intact 'fi'/'fl' left, a clean opinion has hundreds ("first", "find",
    "flight"). So an opinion is broken only if it has at least MIN_HITS repairable words AND more of them than
    intact fi/fl words. A clean opinion that says "fled" five times (a police chase) is NOT broken."""
    hits, intact = counts(text, mapping)
    return hits >= MIN_HITS and intact < hits


def fix_opinion(text, mapping, real=frozenset()):
    """- a broken opinion: every repair, except the real words a broken PDF can still print intact ('rife');
         'fled' IS repaired there, because a broken PDF cannot print the 'fl' of a real 'fled';
       - any other opinion (clean, or partly broken): only the forms that are never real words
         ('specifc'), and only if there are at least MIN_HITS of them; a clean opinion stays as it is."""
    if is_broken(text, mapping):
        use = {w: r for w, r in mapping.items() if not (w in real and can_be_printed_intact(w))}
        return fix_text(text, use)
    fixed, hits = fix_text(text, {w: r for w, r in mapping.items() if w not in real})
    return (fixed, hits) if hits >= MIN_HITS else (text, 0)
