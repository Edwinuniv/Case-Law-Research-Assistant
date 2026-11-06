"""Putting back the letters lost with the PDF ligatures "fi" and "fl".

Some opinions were extracted from PDFs where the single glyph for "fi" or "fl" became a plain "f":
"first" -> "frst", "affirm" -> "affrm", "specific" -> "specifc", "conflict" -> "confict" (Edwin, 2026-11-06:
1,865 passages in 123 decisions). The repair is deliberately narrow:
- the only change is inserting "i" or "l" right after an "f" (that is exactly what the ligature lost);
- the repaired word must be COMMON in the corpus (at least MIN_GOOD times) and far more common than the
  broken word (RATIO times), so a real word such as "lies" or "fed" is never changed;
- only broken opinions are touched: at least MIN_HITS repairable words, and more of them than intact
  fi/fl words (is_broken), so a clean opinion stays exactly as it is, even one that says "fled" often;
- a broken form that could be a real word in a broken PDF too ("rife", "Fred": no 'fi'/'fl' inside) is
  repaired only if the clean opinions almost never use it (final_repairs).
The corpus itself is the dictionary: the 3,500 clean opinions spell the words correctly."""
import re
from collections import Counter

MIN_GOOD, RATIO, MIN_HITS, MIN_LEN = 20, 10, 3, 3
MAX_CLEAN = 2      # see final_repairs
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


def final_repairs(mapping, clean_texts, max_clean=MAX_CLEAN):
    """Drop the repairs that could be a real word: a broken form that a broken PDF can print intact ('rife',
    'Fred') is kept only if the clean opinions (the ones not repaired) almost never use it."""
    clean = vocabulary(clean_texts)
    return {w: r for w, r in mapping.items() if not (can_be_printed_intact(w) and clean.get(w, 0) > max_clean)}


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
    words = [w.lower() for w in WORD.findall(text)]
    hits = sum(1 for w in words if w in mapping)
    intact = sum(1 for w in words if ("fi" in w or "fl" in w) and w not in mapping)
    return hits >= MIN_HITS and intact < hits


def fix_opinion(text, mapping):
    """Repair an opinion only if it is broken (is_broken); otherwise leave it exactly as it is."""
    if not is_broken(text, mapping):
        return text, 0
    return fix_text(text, mapping)
