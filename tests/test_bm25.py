from app.bm25 import BM25

def test_rare_shared_word_ranks_first():
    b = BM25(["the court held the statute valid", "the seventh amendment requires a jury", "the court"])
    scores = b.scores("seventh amendment jury")
    assert scores.argmax() == 1

def test_unknown_words_give_zero():
    assert BM25(["a b c"]).scores("zzz").sum() == 0


def test_saved_index_gives_the_same_scores(tmp_path):
    b = BM25(["the court held the statute valid", "the seventh amendment requires a jury"])
    b.save(tmp_path / "bm25", key="index-1")
    again = BM25.load(tmp_path / "bm25", key="index-1")
    assert list(again.scores("jury amendment")) == list(b.scores("jury amendment"))


def test_saved_index_of_another_search_index_is_not_used(tmp_path):
    BM25(["a b c"]).save(tmp_path / "bm25", key="index-1")
    assert BM25.load(tmp_path / "bm25", key="index-2") is None
    assert BM25.load(tmp_path / "missing", key="index-1") is None


def test_word_forms_match():
    b = BM25(["Chevron is overruled", "the agency interpretation stands"])
    assert b.scores("Did the Court overrule Chevron?").argmax() == 0
    assert b.scores("overruling")[0] > 0
