from app.chunking import chunk_opinion, clean

TEXT = clean("Syllabus\n\nThe syllabus text.\n\nROBERTS, C. J., delivered the opinion of the Court.\n\n"
             "I\n\n" + "First part paragraph. " * 30 + "\n\nII\n\n" + "Second part. " * 500)

def test_offsets_point_exactly_to_chunk_text():
    for c in chunk_opinion(TEXT):
        assert TEXT[c["start"]:c["end"]] == c["text"]

def test_no_chunk_is_much_longer_than_the_limit():
    assert all(len(c["text"].split()) <= 400 for c in chunk_opinion(TEXT, max_words=350))

def test_sections_and_syllabus_are_labelled():
    chunks = chunk_opinion(TEXT)
    assert chunks[0]["is_syllabus"]
    assert any(c["section"] == "Part II" for c in chunks)
    assert not any(c["is_syllabus"] for c in chunks if c["section"].startswith("Part"))

def test_page_furniture_is_removed():
    assert "Cite as" not in clean("Real text.\nCite as: 602 U. S. ____ (2024)\nMore text.")
