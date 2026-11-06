"""Step 4.6 (Edwin's case filter): Searcher.search(..., decision_ids=[...]) only looks at the passages of
those decisions, in BOTH lists; with decision_ids=None nothing changes."""
import numpy as np
from app import config, embeddings
from app.indexing import vector_literal
from app.search import Searcher


class FakeBM25:
    """Keyword scores fixed in advance, one per chunk (same order as Searcher.chunks)."""
    def __init__(self, scores):
        self._scores = np.array(scores, dtype=np.float32)

    def scores(self, question):
        return self._scores.copy()


def keyword_searcher():
    s = Searcher.__new__(Searcher)                     # no database needed for the keyword list
    s.chunks = [{"chunk_id": "a-0", "decision_id": 1}, {"chunk_id": "a-1", "decision_id": 1},
                {"chunk_id": "b-0", "decision_id": 2}, {"chunk_id": "c-0", "decision_id": 3}]
    s.decision_of = np.array([c["decision_id"] for c in s.chunks])
    s.bm25 = FakeBM25([1.0, 0.0, 5.0, 3.0])            # chunk b-0 (decision 2) is the best overall
    return s


def test_keyword_list_without_filter_is_unchanged():
    assert [c for c, _ in keyword_searcher().keyword("q", 10)] == ["b-0", "c-0", "a-0"]


def test_keyword_list_keeps_only_the_given_decisions():
    found = keyword_searcher().keyword("q", 10, decision_ids=[1, 3])
    assert [c for c, _ in found] == ["c-0", "a-0"]                     # b-0 is left out
    assert dict(found) == {"c-0": 3.0, "a-0": 1.0}                     # scores themselves unchanged


def test_keyword_list_with_an_empty_filter_finds_nothing():
    assert keyword_searcher().keyword("q", 10, decision_ids=[]) == []


# ---- the meaning list (pgvector) and the whole search, on the test database ----
def one_hot(i):
    v = np.zeros(384, dtype=np.float32)
    v[i] = 1.0
    return v


def add_passages(db):
    """Two decisions; the passage of decision 2 is the closest in meaning to the question."""
    with db.connect() as con:
        for d in (1, 2):
            con.execute("INSERT INTO decisions (decision_id, all_cluster_ids, case_name, date_filed, licence) "
                        "VALUES (%s, %s, %s, '2020-01-01', 'Public Domain Mark 1.0')", (d, [d], f"Case {d}"))
            con.execute("INSERT INTO opinions (opinion_id, decision_id, label, text, licence) "
                        "VALUES (%s, %s, 'Majority opinion', 'x', 'Public Domain Mark 1.0')", (d, d))
        rows = [("1-0", 1, 1, "speech and the press", 0.6), ("1-1", 1, 1, "speech in schools", 0.3),
                ("2-0", 2, 2, "speech of students", 0.9)]
        for cid, op, d, text, closeness in rows:
            vec = closeness * one_hot(0) + np.sqrt(1 - closeness ** 2) * one_hot(1 + op)
            con.execute("INSERT INTO chunks (chunk_id, opinion_id, decision_id, section, is_syllabus, "
                        "start_char, end_char, text, embedding) VALUES (%s, %s, %s, 'Part I', FALSE, 0, 1, %s, %s)",
                        (cid, op, d, text, vector_literal(vec)))


def test_meaning_list_keeps_only_the_given_decisions(clean_db):
    add_passages(clean_db)
    s = Searcher.__new__(Searcher)
    qvec = vector_literal(one_hot(0))
    assert [c for c, _ in s.dense(qvec, 10)] == ["2-0", "1-0", "1-1"]
    assert [c for c, _ in s.dense(qvec, 10, decision_ids=[1])] == ["1-0", "1-1"]
    assert s.dense(qvec, 10, decision_ids=[]) == []


def test_search_with_filter_same_format_and_cosine_score(clean_db, monkeypatch, tmp_path):
    add_passages(clean_db)
    monkeypatch.setattr(embeddings, "embed_query", lambda text: one_hot(0))
    monkeypatch.setattr(config, "WORK", tmp_path)      # the BM25 cache of this test must not replace the real one
    s = Searcher()
    settings = {"fusion_pool": 50, "w_bm25": 1.0, "w_separate": 1.0}
    everything = s.search("speech", k=10, settings=settings)
    only_1 = s.search("speech", k=10, settings=settings, decision_ids=[1])
    assert {p["decision_id"] for p in everything} == {1, 2}
    assert {p["decision_id"] for p in only_1} == {1}
    assert set(only_1[0]) == set(everything[0])                        # same fields as without the filter
    assert {p["chunk_id"]: p["score"] for p in only_1} == {"1-0": 0.6, "1-1": 0.3}   # still the cosine
