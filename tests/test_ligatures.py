"""Edwin, 2026-11-06: PDF texts lost the "fi"/"fl" ligatures ("frst", "affrm", "specifc", "confict").
The repair puts back an 'i' or an 'l' after an 'f', only when the corpus shows the repaired word is the real one."""
from app import ligatures

CLEAN = ("The first question is whether we affirm. The specific conflict is first. " * 30)   # the dictionary
BROKEN = "We frst ask whether to affrm. The specifc confict is clear. Frst, the FRST point."


def test_lost_fi_and_fl_are_put_back_with_the_case_kept():
    mapping = ligatures.repairs(ligatures.vocabulary([CLEAN, BROKEN]))
    fixed, hits = ligatures.fix_opinion(BROKEN, mapping)
    assert fixed == "We first ask whether to affirm. The specific conflict is clear. First, the FIRST point."
    assert hits == 6


def test_real_words_are_never_changed():
    # "fed" -> "fled" would be a possible repair, but "fed" is a common word itself (as common as "fled"),
    # so it is not broken and stays as it is; words without an "f" ("lies") are never candidates
    text = "The fed fled; the field lies if it flies. " * 40
    mapping = ligatures.repairs(ligatures.vocabulary([text]))
    assert ligatures.fix_text(text, mapping) == (text, 0)


def test_a_repair_needs_the_real_word_to_be_common():
    # "frst" alone, with "first" only twice in the corpus: not enough evidence, nothing changes
    mapping = ligatures.repairs(ligatures.vocabulary(["first first", "frst"]))
    assert "frst" not in mapping


def test_a_clean_opinion_with_one_odd_word_is_left_alone():
    mapping = ligatures.repairs(ligatures.vocabulary([CLEAN, BROKEN]))
    one_odd = "This opinion is clean except one frst word."
    assert ligatures.fix_opinion(one_odd, mapping) == (one_odd, 0)
