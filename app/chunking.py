"""Cleaning opinion text and cutting it into chunks (passages)."""
import re
import warnings
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

# some opinions are stored as XML (field xml_harvard); the HTML parser reads their <p> tags correctly
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

TEXT_FIELDS = ["html_with_citations", "html", "xml_harvard", "html_lawbox",
               "html_columbia", "html_anon_2020", "plain_text"]

OPINION_TYPES = {
    "010combined": "Opinion", "015unamimous": "Unanimous opinion",
    "020lead": "Majority opinion", "025plurality": "Plurality opinion",
    "030concurrence": "Concurring opinion", "035concurrenceinpart": "Concurring in part",
    "040dissent": "Dissenting opinion", "050addendum": "Addendum",
    "060remittitur": "Remittitur", "070rehearing": "Rehearing",
    "080onthemerits": "On the merits", "090onmotiontostrike": "On motion to strike",
}

# lines that are page furniture, not content
JUNK_LINE = re.compile(r"^\s*(Cite as: .*|\d{1,3}|Opinion of the Court|"
                       r"[A-Z ,.'’]+, (C\. )?J\., (dissenting|concurring).*)\s*$")
# The start of each separate opinion inside one text. CourtListener often stores a recent decision
# as ONE "combined" text: majority + concurrences + dissents (e.g. Loper Bright, 2024). Each part
# starts a paragraph like "CHIEF JUSTICE ROBERTS delivered the opinion of the Court." or
# "JUSTICE KAGAN, with whom JUSTICE SOTOMAYOR and JUSTICE JACKSON join,* dissenting."
_WHO = r"(?P<chief>(?i:chief)\s+)?(?i:justice)\s+(?P<name>[A-Z][A-Za-z’'\-]+)"
OPINION_ROLE = re.compile(_WHO + r"(?:,\s*with whom .{0,250}?\bjoins?\b\*?)?,\*?\s*"
                          r"(?P<role>(?:concurring|dissenting|respecting)(?: (?:in|from) [^.,;]{1,80}| the denial[^.,;]{0,60})?)\.")
OPINION_MAIN = re.compile(_WHO + r"\s+(?P<what>delivered the opinion of the Court"
                          r"|announced the judgment of the Court)")
PER_CURIAM = re.compile(r"PER CURIAM\b")
# texts that came from a PDF have no paragraph breaks: the Syllabus starts with this standard note
SYLLABUS_NOTE = re.compile(r"NOTE: Where it is feasible, a syllabus")
# the same opinion starts, found INSIDE a paragraph (281 of 4,709 opinions, e.g. Kennedy v. Bremerton,
# 2022, where "JUSTICE GORSUCH delivered the opinion of the Court." and Sotomayor's dissent sit in the
# middle of one long paragraph)
INLINE_START = re.compile(
    r"(?:(?i:chief)\s+)?(?i:justice)\s+[A-Z][A-Za-z’'\-]+"
    r"(?:\s+(?:delivered the opinion of the Court|announced the judgment of the Court)"
    r"|(?:,\s*with whom .{0,250}?\bjoins?\b\*?)?,\*?\s*(?:concurring|dissenting|respecting)"
    r"(?: (?:in|from) [^.,;]{1,80}| the denial[^.,;]{0,60})?\.)"
    r"|Statement of (?i:justice)\s+[A-Z][A-Za-z’'\-]+\s+respecting"
    r"|NOTE: Where it is feasible, a syllabus")
STATEMENT = re.compile(r"Statement of " + _WHO + r"\s+(?P<role>respecting[^.]{0,80})\.")   # on a denial


def opinion_start(para):
    """If this paragraph starts a separate opinion, return its label, else None."""
    head = para.lstrip()[:400]
    for pattern in (OPINION_ROLE, OPINION_MAIN):
        m = pattern.match(head)
        if m:
            who = m.group("name").title() + (", C. J." if m.group("chief") else ", J.")
            if pattern is OPINION_ROLE:
                return f"{who}, {' '.join(m.group('role').split())}"
            kind = "Opinion of the Court" if m.group("what").startswith("delivered") else "Plurality opinion"
            return f"{kind} ({who[:-4] if who.endswith(', J.') else who[:-7]})"
    m = STATEMENT.match(head)
    if m:
        return f"Statement of {m.group('name').title()}, J., {' '.join(m.group('role').split())}"
    if PER_CURIAM.match(head):
        return "Per curiam"
    if SYLLABUS_NOTE.match(head):
        return "Syllabus"
    return None


HEADING = re.compile(r"^\s*(?:[IVX]{1,6}|[A-H]|\d{1,2})\.?\s*$")


def pick_text(opinion):
    """Return (clean_text, field_used) for the first text field that is not empty."""
    for field in TEXT_FIELDS:
        raw = opinion.get(field) or ""
        if len(raw.strip()) < 200:
            continue
        if field == "plain_text":
            text = raw
        else:
            soup = BeautifulSoup(raw, "lxml")
            blocks = soup.find_all(["p", "blockquote", "h1", "h2", "h3", "h4", "li"])
            if blocks:
                text = "\n\n".join(b.get_text(" ") for b in blocks)
            else:                                    # e.g. text inside <pre>
                text = soup.get_text()
        return clean(text), field
    return "", None


def clean(text):
    lines = [ln for ln in text.replace("\r", "").split("\n") if not JUNK_LINE.match(ln)]
    text = "\n".join(lines)
    text = re.sub(r"-\n(?=[a-z])", "", text)           # re-join words split at line end
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)       # single line breaks -> spaces
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)            # paragraphs separated by one blank line
    return text.strip()


def paragraphs(text):
    """Yield (start, end) of each paragraph in the text."""
    for m in re.finditer(r"[^\n]+", text):
        if m.group(0).strip():
            yield m.start(), m.end()


def split_at_opinion_starts(text, spans):
    """Cut paragraphs where an opinion starts in the middle of them (texts from PDFs)."""
    for s, e in spans:
        cuts = [s] + [m.start() for m in INLINE_START.finditer(text, s, e)
                      if m.start() > s and text[m.start() - 1].isspace()] + [e]
        for a, b in zip(cuts, cuts[1:]):
            while a < b and text[a].isspace():
                a += 1
            while b > a and text[b - 1].isspace():
                b -= 1
            if a < b:
                yield a, b


def sentences(text, start, end):
    """Split one long paragraph into sentence spans."""
    pos = start
    for m in re.finditer(r"(?<=[.?!])[\"”’)]?\s+(?=[A-Z“\"(])", text[start:end]):
        yield pos, start + m.start()
        pos = start + m.end()
    yield pos, end


def section_is_not_syllabus(units):
    """True unless we are already in the Syllabus. In slip opinions "Syllabus" is also a running
    header repeated on every page; repeating it must not cut the Syllabus into tiny chunks."""
    for kind, label, _, _ in reversed(units):
        if kind in ("HEADING", "OPINION"):
            return label != "Syllabus"
    return True


def chunk_opinion(text, max_words=350):
    """Cut ONE opinion into chunks of whole paragraphs (about max_words words each).
    Returns a list of dicts with exact character positions (start, end) in `text`."""
    units, section, opinion = [], "Opening", None
    for s, e in split_at_opinion_starts(text, paragraphs(text)):
        para = text[s:e].strip()
        label = opinion_start(para)
        if label == "Syllabus":                             # Syllabus note in a text from a PDF
            if section_is_not_syllabus(units):
                units.append(("HEADING", "Syllabus", s, s))
        elif label:                                         # a new opinion starts here
            units.append(("OPINION", label, s, e))
        if HEADING.match(para):
            units.append(("HEADING", para, s, e))
            continue
        if re.match(r"^\s*syllabus\s*$", para, re.I):
            if not (units and units[-1][1] == "Syllabus") and section_is_not_syllabus(units):
                units.append(("HEADING", "Syllabus", s, e))
            continue
        if len(para.split()) > max_words:                  # very long paragraph -> sentences
            for ss, se in sentences(text, s, e):
                units.append(("TEXT", None, ss, se))
        else:
            units.append(("TEXT", None, s, e))

    chunks, current = [], []

    def flush():
        if current:
            s, e = current[0][0], current[-1][1]
            chunks.append({"start": s, "end": e, "section": section,
                           "is_syllabus": section == "Syllabus", "text": text[s:e]})

    for kind, label, s, e in units:
        if kind == "OPINION":
            flush(); current = []
            opinion = section = label
            continue
        if kind == "HEADING":
            flush(); current = []
            if label == "Syllabus":
                section = "Syllabus"
            else:
                section = f"{opinion} - Part {label}" if opinion else f"Part {label}"
            continue
        if section == "Syllabus" and re.search(r"delivered the opinion of the Court", text[s:e]):
            current.append((s, e))          # the Syllabus's last line ("X delivered the opinion...")
            flush(); current = []           # belongs to the Syllabus; the opinion starts after it
            section = "Opening"
            continue
        words_now = sum(len(text[a:b].split()) for a, b in current)
        if current and words_now + len(text[s:e].split()) > max_words:
            flush(); current = []
        current.append((s, e))
    flush()
    return chunks
