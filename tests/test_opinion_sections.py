"""Step 2.1 (fix): one text can hold several opinions (majority, concurrences, dissents).
Found on Loper Bright (2024): its concurrences and the dissent were labelled like the majority."""
from app.chunking import chunk_opinion, clean, opinion_start

COMBINED = clean(
    "Syllabus\n\nHeld: Chevron is overruled. " + "Syllabus text. " * 30 + "\n\nSyllabus\n\n"
    "ROBERTS, C. J., delivered the opinion of the Court, in which THOMAS, J., joined.\n\n"
    "CHIEF JUSTICE ROBERTS delivered the opinion of the Court. " + "Majority text. " * 100 + "\n\n"
    "JUSTICE GORSUCH, concurring. " + "Concurrence text. " * 50 + "\n\n"
    "JUSTICE KAGAN, with whom JUSTICE SOTOMAYOR and JUSTICE JACKSON join,* dissenting. " + "Dissent text. " * 50)


def test_each_opinion_gets_its_own_label():
    chunks = chunk_opinion(COMBINED)
    sections = [c["section"] for c in chunks]
    assert sections[0] == "Syllabus"
    assert "Opinion of the Court (Roberts)" in sections
    assert "Gorsuch, J., concurring" in sections
    assert "Kagan, J., dissenting" in sections


def test_a_chunk_never_mixes_two_opinions():
    for c in chunk_opinion(COMBINED):
        kinds = {k for k in ("Majority", "Concurrence", "Dissent") if f"{k} text" in c["text"]}
        assert len(kinds) <= 1, c["section"]
        assert COMBINED[c["start"]:c["end"]] == c["text"]


def test_repeated_syllabus_page_headers_keep_one_syllabus():
    chunks = chunk_opinion(COMBINED)
    assert sum(c["is_syllabus"] for c in chunks) == 1
    assert "delivered the opinion of the Court, in which" in chunks[0]["text"]


def test_sentences_that_only_mention_a_justice_are_not_boundaries():
    assert opinion_start("Justice Kagan's dissent argues that Chevron was right.") is None
    assert opinion_start("Justice Stevens, dissenting, contends that the statute is clear.") is None
    assert opinion_start("ROBERTS, C. J., delivered the opinion of the Court, in which") is None


def test_opinions_on_a_denial_of_certiorari_are_labelled():
    assert opinion_start("JUSTICE GORSUCH, dissenting from the denial of certiorari. This") == \
        "Gorsuch, J., dissenting from the denial of certiorari"
    assert opinion_start("Statement of JUSTICE ALITO respecting the denial of certiorari. I") == \
        "Statement of Alito, J., respecting the denial of certiorari"
