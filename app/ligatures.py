"""Putting back the letters lost with the PDF ligatures "fi" and "fl".

Some opinions were extracted from PDFs where the single glyph for "fi" or "fl" became a plain "f":
"first" -> "frst", "affirm" -> "affrm", "specific" -> "specifc", "conflict" -> "confict" (Edwin, 2026-11-06:
1,865 passages in 123 decisions). The repair is deliberately narrow:
- the only change is inserting "i" or "l" right after an "f" (that is exactly what the ligature lost);
- the repaired word must be COMMON in the corpus (at least MIN_GOOD times) and far more common than the
  broken word (RATIO times), so a real word such as "lies" or "fed" is never changed;
- only opinions with at least MIN_HITS repaired words are touched, so a clean opinion with one odd word
  stays exactly as it is.
The corpus itself is the dictionary: the 3,500 clean opinions spell the words correctly."""
import re
from collections import Counter

MIN_GOOD, RATIO, MIN_HITS, MIN_LEN = 20, 10, 3, 3
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


def fix_opinion(text, mapping):
    """Repair an opinion only if it clearly has the problem (at least MIN_HITS repaired words)."""
    fixed, hits = fix_text(text, mapping)
    return (fixed, hits) if hits >= MIN_HITS else (text, 0)
