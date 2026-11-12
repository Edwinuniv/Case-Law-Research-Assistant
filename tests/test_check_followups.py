"""The checker of eval/followups.jsonl (followups-v1), written from the expected behaviour before the code.
A pair = a first question and a follow-up about its answer (EVALUATION.md, follow-up questions rule).
No database: the opinion texts are given by a small function, like the citation index in other tests."""

TEXTS = {111: "The Court held that the statute is unconstitutional. Justice X, dissenting, wrote otherwise."}

def texts(ids):
    return [TEXTS[i] for i in ids if i in TEXTS]

GOOD = {"id": "F001", "tag": "answerable", "split": "tune", "kind": "separate_opinion", "author": "Edwin",
        "first_question": "Did the Court strike down the statute?", "follow_up": "What did the dissent say about it?",
        "expected_answer": "The dissent disagreed.", "gold_decision_ids": [111],
        "gold_quote": "Justice X, dissenting, wrote otherwise.", "must_not_appear": [], "why": ""}

def problems(pair):
    from scripts.check_followups import pair_problems
    return pair_problems(pair, texts)


def test_a_good_pair_has_no_problem():
    assert problems(GOOD) == []

def test_every_kind_of_the_rule_is_known_and_nothing_else():
    from scripts.check_followups import KINDS
    assert set(KINDS) == {"explain", "separate_opinion", "missing_detail", "false_premise", "invent_case", "injection"}
    assert any("kind" in p for p in problems({**GOOD, "kind": "chit_chat"}))

def test_required_fields_depend_on_the_tag():
    assert any("gold_quote" in p for p in problems({**GOOD, "gold_quote": ""}))
    unanswerable = {**GOOD, "tag": "unanswerable", "kind": "missing_detail", "gold_quote": "", "gold_decision_ids": [],
                    "expected_answer": "", "why": ""}
    assert any("why" in p for p in problems(unanswerable))
    adversarial = {**GOOD, "tag": "adversarial", "kind": "false_premise", "why": "false premise"}
    del adversarial["must_not_appear"]
    assert any("must_not_appear" in p for p in problems(adversarial))

def test_both_questions_follow_the_length_rule_and_differ():          # SR3: 3 to 1,000 characters
    assert any("first_question" in p for p in problems({**GOOD, "first_question": "ab"}))
    assert any("follow_up" in p for p in problems({**GOOD, "follow_up": "x" * 1001}))
    assert any("same" in p for p in problems({**GOOD, "follow_up": GOOD["first_question"]}))

def test_the_gold_quote_must_be_word_for_word_in_a_gold_decision():
    assert any("NOT FOUND word for word" in p for p in problems({**GOOD, "gold_quote": "The dissent agreed with everything."}))
    assert any("decision NOT FOUND" in p for p in problems({**GOOD, "gold_decision_ids": [999]}))

def test_split_id_and_author_are_checked():                           # written by the team: the author is required
    assert any("split" in p for p in problems({**GOOD, "split": "train"}))
    assert any("id" in p for p in problems({**GOOD, "id": "A001"}))      # F ids, apart from eval-v1's A/U/X
    assert any("author" in p for p in problems({**GOOD, "author": ""}))

def test_a_file_reports_duplicates_and_bad_json_and_counts():
    from scripts.check_followups import check_lines
    import json
    lines = [json.dumps(GOOD), json.dumps(GOOD), "{not json", ""]
    report = check_lines(lines, texts)
    assert report["problems"]["F001 (line 2)"] == ["duplicate id"] and "line 3" in report["problems"]
    assert report["counts"] == {("answerable", "tune"): 2} and report["authors"] == {"Edwin": 2}

def test_the_empty_file_is_valid_and_says_so():
    from scripts.check_followups import check_lines
    assert check_lines([], texts) == {"problems": {}, "counts": {}, "authors": {}, "pairs": 0}
