"""The summaries-v1 set (EVALUATION.md "Passage summaries"): 14 requests, each after an answerable TUNE question of
eval-v1, approved by Edwin on 2026-11-21 and tagged before the measurement. Checks the file, not the code's answers."""
import json
from app.pipeline import passage_request

SET = [json.loads(line) for line in open("eval/summaries.jsonl") if line.strip()]
QUESTIONS = {json.loads(line)["id"]: json.loads(line) for line in open("eval/questions.jsonl") if line.strip()}
EXPECTED = {"passage": 1, "two passages": 2, "all passages": 3, "citation": 1, "opinion: dissent": 1,
            "opinion: majority": 1, "case": 1}                 # 5 + 2 + 3 of the rule, then the 4 of the widened rule


def test_fourteen_requests_with_unique_ids_and_the_rules_mix():
    assert len(SET) == 14 and len({r["id"] for r in SET}) == 14
    kinds = [r["kind"] for r in SET]
    assert {k: kinds.count(k) for k in set(kinds)} == {"passage": 5, **{k: v for k, v in EXPECTED.items() if k != "passage"}}


def test_each_first_question_is_an_answerable_tune_question_of_eval_v1_word_for_word():
    for r in SET:
        q = QUESTIONS[r["first_id"]]
        assert q["split"] == "tune" and q["tag"] == "answerable" and r["first"] == q["question"] and r["split"] == "tune"


def test_each_request_is_recognised_as_its_kind():
    for r in SET:
        which = passage_request(r["request"])
        kind = r["kind"]
        if kind == "passage":
            assert which and len(which) == 1 and which != ["all"], r["id"]
        elif kind == "two passages":
            assert which and len(which) == 2, r["id"]
        elif kind == "all passages":
            assert which == ["all"], r["id"]
        elif kind == "citation":
            assert which == ["C1"], r["id"]
        elif kind.startswith("opinion"):
            assert which == [f"opinion:{kind.split(': ')[1]}"], r["id"]
        else:
            assert which == ["case"], r["id"]
