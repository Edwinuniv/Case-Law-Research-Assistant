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


def sentences(text, start, end):
    """Split one long paragraph into sentence spans."""
    pos = start
    for m in re.finditer(r"(?<=[.?!])[\"”’)]?\s+(?=[A-Z“\"(])", text[start:end]):
        yield pos, start + m.start()
        pos = start + m.end()
    yield pos, end


def chunk_opinion(text, max_words=350):
    """Cut ONE opinion into chunks of whole paragraphs (about max_words words each).
    Returns a list of dicts with exact character positions (start, end) in `text`."""
    units, section = [], "Opening"
    for s, e in paragraphs(text):
        para = text[s:e].strip()
        if HEADING.match(para):
            units.append(("HEADING", para, s, e))
            continue
        if re.match(r"^\s*syllabus\s*$", para, re.I):
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
        if kind == "HEADING":
            flush(); current = []
            section = label if label == "Syllabus" else f"Part {label}"
            continue
        if section == "Syllabus" and re.search(r"delivered the opinion of the Court", text[s:e]):
            flush(); current = []
            section = "Opening"
        words_now = sum(len(text[a:b].split()) for a, b in current)
        if current and words_now + len(text[s:e].split()) > max_words:
            flush(); current = []
        current.append((s, e))
    flush()
    return chunks
