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


def test_words_that_can_be_real_in_a_broken_pdf_need_the_clean_opinions_to_agree():
    """Yasser's dry run: 'rife' -> 'rifle' and 'fred' -> 'fired' were proposed. 'rife' and 'Fred' contain no
    'fi'/'fl', so a broken PDF prints them intact: they are repaired only if the clean opinions never use them.
    'fled' contains 'fl', which a broken PDF cannot print, so there it can only be 'filed'."""
    clean = ["The suspect fled. The report was rife with errors. Fred testified. " * 5,
             "The brief was filed first. The rifle was fired. The filing was late. " * 80]
    broken = "The motion was fled. The brief was fled. The rife was fred. Frst, the fling deadline."
    first = ligatures.repairs(ligatures.vocabulary(clean + [broken]))
    mapping = ligatures.final_repairs(first, clean)
    fixed, _ = ligatures.fix_opinion(broken, mapping)
    assert "was filed. The brief was filed." in fixed               # 'fled' -> 'filed' inside the broken PDF
    assert "The rife was fred." in fixed                            # ambiguous: left as it is
    assert "rife" not in mapping and "fred" not in mapping


def test_a_clean_opinion_that_often_says_fled_is_not_touched():
    """A police chase: 'fled' five times, but also many intact fi/fl words, so it is not a broken PDF."""
    corpus = ["The brief was filed first. The filing was late. " * 80]
    chase = "The suspect fled. He fled again, then fled on foot, fled the officers and fled. " \
            "The officer was the first to find him; the flight ended in a field. The final finding stood."
    mapping = ligatures.repairs(ligatures.vocabulary(corpus + [chase]))
    assert mapping.get("fled") == "filed"                     # 'fled' is a known repair...
    assert ligatures.fix_opinion(chase, mapping) == (chase, 0)   # ...but this opinion is not broken
