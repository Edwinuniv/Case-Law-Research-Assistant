"""Finding citations in text, normalising them, and checking whether they exist."""
import re
from functools import lru_cache
from eyecite import get_citations
from eyecite.models import FullCaseCitation
from app import db

# Anything that LOOKS like a citation: number + words + number ("12 Fake Rep. 345").
# eyecite only knows real reporter names, so this also catches invented ones.
CITATION_LIKE = re.compile(r"\b\d{1,3}\s+(?:[A-Z][A-Za-z0-9.]*\s?){1,4}\s*(?:\d{1,5}|_{2,})\b")
# Case names like "Smith v. Jones"
CASE_NAME = re.compile(r"\b([A-Z][\w.'&-]*(?:\s+(?:of|the|and|[A-Z][\w.'&-]*)){0,5})\s+v\.\s+"
                       r"([A-Z][\w.'&-]*(?:\s+(?:of|the|and|[A-Z][\w.'&-]*)){0,5})")
LEADING_WORDS = re.compile(r"^(?:(?:In|See|Under|The|Cf\.?|As|But|And|Also|Like|Both|Unlike|"
                           r"Following|Citing|Per|After|Before|While|When)\s+)+")


def parse(citation_text):
    """'603 U. S. 593' -> ('603', 'U.S.', '593'), or None if eyecite cannot read it (SR13)."""
    if not (citation_text or "").strip():
        return None
    for c in get_citations(citation_text):
        if isinstance(c, FullCaseCitation) and c.groups.get("page"):
            return c.groups["volume"], c.corrected_reporter(), c.groups["page"]
    return None


def normalise(citation_text):
    p = parse(citation_text)
    return " ".join(p) if p else None


def find_citations(text):
    """Every citation-like string in a text (normalised when eyecite can read it)."""
    found = set()
    if not (text or "").strip():
        return found
    for c in get_citations(text):
        if isinstance(c, FullCaseCitation):
            found.add(c.corrected_citation())
    for m in CITATION_LIKE.finditer(text):
        found.add(normalise(m.group(0)) or re.sub(r"\s+", " ", m.group(0)))
    return found


def find_case_names(text):
    return [LEADING_WORDS.sub("", m.group(0)) for m in CASE_NAME.finditer(text or "")]


def name_words(name):
    return re.sub(r"[^a-z0-9 ]+", " ", (name or "").lower()).split()


class CitationIndex:
    """Answers: which cluster does this citation point to, and is it one of our decisions?"""

    def __init__(self):
        with db.connect() as con:
            self.alias = {r["cluster_id"]: r["decision_id"]
                          for r in con.execute("SELECT cluster_id, decision_id FROM cluster_alias")}
            self.case_names = [r["case_name"] for r in con.execute("SELECT case_name FROM decisions")]

    @lru_cache(maxsize=20_000)
    def cluster_for(self, citation_text):
        p = parse(citation_text)
        if not p:
            return None
        with db.connect() as con:
            row = con.execute("SELECT cluster_id FROM citations WHERE reporter = %s AND volume = %s "
                              "AND page = %s LIMIT 1", (p[1], p[0], p[2])).fetchone()
        return row["cluster_id"] if row else None

    def decision_for_cluster(self, cluster_id):
        return self.alias.get(cluster_id)

    def lookup(self, citation_text):
        """The four answers of the citation lookup page (SR14)."""
        key = normalise(citation_text)
        if key is None:
            return {"status": "CANNOT BE READ", "citation": citation_text}
        cluster = self.cluster_for(key)
        if cluster is None:
            return {"status": "NOT FOUND", "citation": key}
        decision = self.decision_for_cluster(cluster)
        if decision:
            return {"status": "IN OUR CORPUS", "citation": key, "cluster_id": cluster, "decision_id": decision}
        return {"status": "EXISTS OUTSIDE OUR CORPUS", "citation": key, "cluster_id": cluster}

    def known_case_name(self, name):
        words = name_words(name)
        return bool(words) and any(name_words(n)[:1] == words[:1] for n in self.case_names)


class StaticCitationIndex(CitationIndex):
    """The same interface without a database: used by the tests."""

    def __init__(self, citations, alias, case_names):
        self.table, self.alias, self.case_names = citations, alias, case_names

    def cluster_for(self, citation_text):
        return self.table.get(normalise(citation_text))
