"""Decisions that are not Supreme Court decisions of 2000-2024, although CourtListener files them so.

Found on 2026-11-07 by two citation rules (scripts/check_scope.py):
- a U.S. Reports volume below 528 means a decision from before 2000 (volume 528 covers early 2000):
  CourtListener gave these old cases a date in 2005-2010;
- citations only in lower-court reporters (F., F.2d, F.3d, F. App'x, F. Supp.) mean another court.
Every hit is checked by hand: the list below says what each one really is. Two hits are real 2016
decisions whose S. Ct. citation CourtListener stored as "U.S." (REVIEWED_IN_SCOPE)."""
import re

OUT_OF_SCOPE = {
    1982974: "Hamburg-American Co. v. United States, 277 U.S. 138 (1928), filed under 2005",
    1289341: "Aikens v. Wisconsin, 195 U.S. 194 (1904), filed under 2005",
    98012: "New York v. Lawson Purdy, 231 U.S. 373 (1913), filed under 2005",
    2351745: "Quebec Bank of Toronto v. Hellman, 110 U.S. 178 (1884), filed under 2007",
    1960562: "Ames v. Kansas ex rel. Johnston, 111 U.S. 449 (1884), filed under 2010",
    2621081: "Myers v. Anderson, 238 U.S. 368 (1915), filed under 2010",
    1447389: "Fisher ex rel. Barcelon v. Baker, 203 U.S. 174 (1906), filed under 2010",
    8694154: "JPMorgan Chase Bank v. Winget, 602 F. App'x 246 (6th Cir. 2015), not the Supreme Court",
}
REVIEWED_IN_SCOPE = {
    3181500: "Gobeille v. Liberty Mutual, 577 U.S. 312 (2016): '136 U.S. 936' is 136 S. Ct. 936",
    3181499: "Lockhart v. United States, 577 U.S. 347 (2016): '136 U.S. 958' is 136 S. Ct. 958",
}
FIRST_VOLUME = 528                       # the first U.S. Reports volume with decisions of 2000
US_CITE = re.compile(r"^(\d+) U\. ?S\. \d+")
SCOTUS_REPORTER = re.compile(r"\bU\. ?S\.|S\. ?Ct\.|L\. ?Ed\.|U\.S\. LEXIS")
LOWER_REPORTER = re.compile(r"\bF\. ?(?:App'x|Supp\.?|[234]d|4th)?\s\d|\bF\.\s?\d")


def old_us_citation(citations):
    """The first U.S. Reports citation from before 2000, or None."""
    for c in citations:
        m = US_CITE.match(c)
        if m and int(m.group(1)) < FIRST_VOLUME:
            return c
    return None


def lower_court_only(citations):
    """True if the decision is cited only in lower-court reporters."""
    return bool(citations) and not any(SCOTUS_REPORTER.search(c) for c in citations) \
        and any(LOWER_REPORTER.search(c) for c in citations)


def problems(decision_id, citations):
    """Why this decision may be out of scope (empty list = no problem, or already reviewed as in scope)."""
    if decision_id in REVIEWED_IN_SCOPE:
        return []
    found = []
    old = old_us_citation(citations)
    if old:
        found.append(f"U.S. Reports volume before 2000 ({old})")
    if lower_court_only(citations):
        found.append(f"only lower-court citations ({', '.join(citations)})")
    return found
