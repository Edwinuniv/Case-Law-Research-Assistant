"""Step 3.3 (settings): weighted fusion of the two lists. Defaults must give the plain RRF baseline."""
from app.search import Searcher


def searcher(sections):
    s = Searcher.__new__(Searcher)                    # no database needed for the fusion itself
    s.by_id = {cid: {"section": sec, "opinion_label": "Opinion"} for cid, sec in sections.items()}
    return s


SECTIONS = {"majority": "Opinion of the Court (Roberts)", "dissent": "Kagan, J., dissenting",
            "other": "Opening"}
DENSE = [("dissent", 0.9), ("other", 0.8), ("majority", 0.7)]
KEYWORD = [("majority", 9.0), ("dissent", 5.0), ("other", 1.0)]
BASE = {"w_bm25": 1.0, "w_separate": 1.0, "fusion_pool": 50}


def test_defaults_are_plain_reciprocal_rank_fusion():
    # dissent: 1/61 + 1/62, majority: 1/63 + 1/61, other: 1/62 + 1/63
    assert searcher(SECTIONS).fuse(DENSE, KEYWORD, 3, BASE) == ["dissent", "majority", "other"]


def test_lower_weight_for_separate_opinions_puts_the_court_first():
    order = searcher(SECTIONS).fuse(DENSE, KEYWORD, 3, {**BASE, "w_separate": 0.5})
    assert order[0] == "majority" and order[-1] == "dissent"


def test_higher_keyword_weight_follows_bm25():
    order = searcher(SECTIONS).fuse(DENSE, KEYWORD, 3, {**BASE, "w_bm25": 3.0})
    assert order == ["majority", "dissent", "other"]


def test_pool_limits_the_candidates():
    assert searcher(SECTIONS).fuse(DENSE, KEYWORD, 3, {**BASE, "fusion_pool": 1}) == ["dissent", "majority"]


def test_passages_of_top_decisions_takes_every_passage_of_the_first_decisions():
    s = Searcher.__new__(Searcher)
    s.chunks = [{"chunk_id": f"{d}-{i}", "decision_id": d} for d in (1, 2, 3) for i in range(3)]
    found = [{"decision_id": 2}, {"decision_id": 2}, {"decision_id": 3}, {"decision_id": 1}]
    got = s.passages_of_top_decisions(found, 2)
    assert {c["decision_id"] for c in got} == {2, 3} and len(got) == 6
