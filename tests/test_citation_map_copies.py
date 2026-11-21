"""Citation-map rows of skipped copies (SPEC 11, 2026-11-21): written from the rule before the code.
copy_targets(copy, ours) says which of OUR opinions of a decision receive the map rows of a copy we skipped."""
from app.ingest import copy_targets, shingles


def text(start, n=400):
    """A text of n distinct words: two texts with different starts share no 5-word sequence."""
    return " ".join(f"w{i}" for i in range(start, start + n))


MAJORITY, DISSENT = text(0), text(10_000)


def ours(**texts):
    return {oid: shingles(t) for oid, t in texts.items()}


def test_a_copy_of_our_majority_goes_to_the_majority_only():
    copy = shingles(MAJORITY + " a few words the other copy does not have")       # rule 1: same text
    assert copy_targets(copy, ours(majority=MAJORITY, dissent=DISSENT)) == ["majority"]


def test_the_closest_of_two_similar_opinions_wins():
    near = MAJORITY + " " + text(20_000, 40)                                     # both pass 0.6, one is closer
    far = MAJORITY + " " + text(30_000, 150)
    assert copy_targets(shingles(MAJORITY), ours(near=near, far=far)) == ["near"]


def test_a_combined_copy_goes_to_each_opinion_it_contains():
    combined = shingles(MAJORITY + " " + DISSENT)                                 # rule 2
    assert sorted(copy_targets(combined, ours(majority=MAJORITY, dissent=DISSENT))) == ["dissent", "majority"]


def test_a_part_goes_to_the_combined_text_we_kept():
    kept = MAJORITY + " " + DISSENT + " " + text(40_000)                          # rule 3: the copy is one part
    assert copy_targets(shingles(DISSENT), ours(combined=kept, other=text(50_000))) == ["combined"]


def test_an_unrelated_copy_goes_to_nobody():
    assert copy_targets(shingles(text(60_000)), ours(majority=MAJORITY, dissent=DISSENT)) == []     # rule 4


def test_a_decision_with_no_opinion_of_ours_gives_nobody():
    assert copy_targets(shingles(MAJORITY), {}) == []
