"""Edwin, run 2 (AI_LOG 2026-11-08): correct quotes failed the word-for-word check because our text has
words broken at a line end ("mar- riage", about 4,000 passages) and CourtListener page markers inside
sentences ("authority, *490 however", 22,235 passages). Expected behaviour, written before the code:
- a broken word is joined only when the corpus shows the joined word is the real one ("marriage");
- a compound broken at its own hyphen keeps the hyphen ("self- incrimination" -> "self-incrimination");
- anything else stays as it is ("pre- and post-trial" is real English);
- a page marker "*490" or "**12" inside the text is removed, a footnote star or a number is not."""
from app import linebreaks

CLEAN = ("The right to marriage is fundamental. The marriage laws were struck down. "
         "The privilege against self-incrimination applies. Self-incrimination is barred. "
         "The constitution protects marriage. The statute constitutes a taking. ") * 30


def fix(text, corpus=(CLEAN,)):
    mapping = linebreaks.repairs(linebreaks.vocabulary(list(corpus) + [text]))
    return linebreaks.fix_text(text, mapping)


def test_a_broken_word_is_joined_when_the_corpus_knows_the_word():
    assert fix("The right to mar- riage, which consti- tutes a liberty.") == \
        ("The right to marriage, which constitutes a liberty.", 2)


def test_the_case_of_the_first_part_is_kept():
    assert fix("Mar- riage is a right.")[0] == "Marriage is a right."


def test_a_compound_broken_at_its_hyphen_keeps_the_hyphen():
    assert fix("the privilege against self- incrimination")[0] == "the privilege against self-incrimination"


def test_unknown_or_real_hyphen_space_forms_stay():
    for text in ("pre- and post-trial review", "the zorb- wabble rule", "state- and federal courts"):
        assert fix(text) == (text, 0)


def test_page_markers_inside_the_text_are_removed():
    assert linebreaks.remove_page_markers("the authority, *490 however, is clear") == \
        ("the authority, however, is clear", 1)
    assert linebreaks.remove_page_markers("as we held. **12 The next point") == ("as we held. The next point", 1)


def test_footnote_stars_numbers_and_arithmetic_are_not_page_markers():
    for text in ("the rule.* See note", "in 1990 the Court", "a 2*3 grid", "Section 1983"):
        assert linebreaks.remove_page_markers(text) == (text, 0)


def test_pinpoint_citations_to_databases_are_not_page_markers():
    """Yasser's dry run on the real corpus: "*4" in "1978 U. S. Dist. LEXIS 19296, *4 (SDNY ...)",
    "1988 WL 44736, *2 (CA6 1988)" and "Id., at *1" are pinpoint citations to an unpaginated database
    (the page of the LEXIS or Westlaw document), part of a legal citation. They must stay."""
    for text in ("1978 U. S. Dist. LEXIS 19296, *4 (SDNY, Mar. 1, 1978); accord",
                 "No. 86-1809, 1988 WL 44736, *2 (CA6 1988) (holding that",
                 "under §2255. Id., at *1 (internal quotation marks omitted)"):
        assert linebreaks.remove_page_markers(text) == (text, 0)
    # a real page marker in a sentence is still removed (after a word and a comma: tested above)
    assert linebreaks.remove_page_markers("deviated radically *25 from the terms") == \
        ("deviated radically from the terms", 1)


def test_fix_opinion_does_both_and_counts_each():
    text = "The right to mar- riage, *490 which the statute consti- tutes."
    mapping = linebreaks.repairs(linebreaks.vocabulary([CLEAN, text]))
    fixed, words, markers = linebreaks.fix_opinion(text, mapping)
    assert fixed == "The right to marriage, which the statute constitutes."
    assert (words, markers) == (2, 1)
