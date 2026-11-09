"""Joining words broken at a line end, and removing CourtListener page markers.

Edwin's run 2 (AI_LOG 2026-11-08): some texts keep a word broken at the end of a printed line with a
space after the hyphen ("mar- riage", about 4,000 passages), and star-pagination markers inside
sentences ("authority, *490 however", 22,235 passages). A correct quote of such a text fails the
word-for-word check, and the reader sees the broken text. The repair is narrow, like app/ligatures.py:
- "word- word" is joined only if the corpus shows the joined word is the real one: it is used at least
  MIN_GOOD times, and RATIO times more than the hyphenated form ("mar- riage" -> "marriage");
- if instead the hyphenated form is the common one, only the space goes ("self- incrimination" ->
  "self-incrimination": the line break fell on a real hyphen);
- anything else stays ("pre- and post-trial" is real English);
- a page marker is a star (or two) and a page number standing alone between spaces ("*490", "**12");
  a footnote star after a word ("rule.*") or a star between numbers ("2*3") is not one, and neither is a
  pinpoint citation to a LEXIS or Westlaw page ("1988 WL 44736, *2", "Id., at *1": Yasser's dry run).
The corpus itself is the dictionary: most texts spell these words on one line."""
import re
from collections import Counter

MIN_GOOD, RATIO = 20, 10
WORD = re.compile(r"[a-z]+(?:-[a-z]+)*")                 # "marriage", "self-incrimination"
BROKEN = re.compile(r"\b([A-Za-z]+)- ([a-z]+)\b")        # "mar- riage", "Self- incrimination"
# " *490" before a space; not a pinpoint citation to a database page: "LEXIS 19296, *4", "WL 44736, *2"
# (a number and a comma before it) or "Id., at *1" (the word "at" before it)
PAGE_MARKER = re.compile(r"(?<!\d,)(?<!\bat) \*{1,2}\d{1,4}(?= )")


def vocabulary(texts):
    """How often each lower-case word appears in all the texts (a hyphenated word counts as one word),
    and, under a (first part, second part) key, how often each broken pair "word- word" appears."""
    counts = Counter()
    for text in texts:
        counts.update(WORD.findall(text.lower()))
        counts.update((m.group(1).lower(), m.group(2)) for m in BROKEN.finditer(text))
    return counts


def repairs(vocab):
    """(first part, second part) -> repaired word, for the broken pairs that pass the rules above."""
    mapping = {}
    for key in vocab:
        if not isinstance(key, tuple):
            continue
        a, b = key
        joined, hyphen = a + b, f"{a}-{b}"
        if vocab.get(joined, 0) >= MIN_GOOD and vocab[joined] >= RATIO * vocab.get(hyphen, 0):
            mapping[key] = joined
        elif vocab.get(hyphen, 0) >= MIN_GOOD:
            mapping[key] = hyphen
    return mapping


def fix_text(text, mapping):
    """The text with every known broken pair repaired (case of the first letter kept), and how many."""
    hits = 0

    def swap(m):
        nonlocal hits
        fixed = mapping.get((m.group(1).lower(), m.group(2)))
        if fixed is None:
            return m.group(0)
        hits += 1
        return fixed[0].upper() + fixed[1:] if m.group(1)[0].isupper() else fixed
    return BROKEN.sub(swap, text), hits


def remove_page_markers(text):
    """The text without star-pagination markers, and how many were removed."""
    return PAGE_MARKER.subn("", text)


def fix_opinion(text, mapping):
    """(fixed text, broken words joined, page markers removed)."""
    text, words = fix_text(text, mapping)
    text, markers = remove_page_markers(text)
    return text, words, markers
