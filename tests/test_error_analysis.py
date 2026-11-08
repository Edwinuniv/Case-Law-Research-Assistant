"""Step 8.2, error analysis: why each answerable TUNE question was answered "not supported", and which
unanswerable TUNE questions were answered. Written from the expected behaviour, before the code."""
from app.config import DEFAULT_SETTINGS
from tests.test_evaluate import res, q

S = dict(DEFAULT_SETTINGS)


def tune(i, tag="answerable"):
    return {**q(i, tag), "split": "tune"}


def removed_all(*problems):
    return {**res(0.0, kept=0), "removed": [{"text": "s", "sources": ["P1"], "problems": list(problems)}]}


def analyse(pairs, quote_found=lambda q: True):
    from scripts.error_analysis import analyse
    return analyse(pairs, S, quote_found)


def test_each_abstention_gets_one_cause_in_pipeline_order():
    pairs = [(tune("gate"), res(0.9, top=0.1)),                    # below the gate, even if the model said yes
             (tune("model"), res(0.9, said="NOT_SUPPORTED")),
             (tune("removed"), removed_all("quote not found in the cited passage")),
             (tune("tau"), res(0.4)),
             (tune("fine"), res(0.9))]                             # answered: not an error
    causes = {x["id"]: x["cause"] for x in analyse(pairs)["abstained_but_should_answer"]}
    assert causes == {"gate": "below the retrieval gate", "model": "the model said the passages do not answer",
                      "removed": "every sentence removed by the verifier", "tau": "support score under tau_abstain"}


def test_verifier_problems_are_counted_by_kind():
    pairs = [(tune("a"), removed_all("quote not found in the cited passage", "number or date not in the cited passage: 5")),
             (tune("b"), removed_all("quote not found in the cited passage"))]
    assert analyse(pairs)["verifier_problems"] == {"quote not found in the cited passage": 2,
                                                    "number or date not in the cited passage": 1}


def test_only_the_tune_split_is_read():                             # SR29: TEST is reported once, elsewhere
    seen = []
    pairs = [(q("t", "answerable"), res(0.1)), (q("u", "unanswerable"), res(0.9)), (tune("a"), res(0.1))]
    out = analyse(pairs, lambda x: seen.append(x["id"]) or True)
    assert [x["id"] for x in out["abstained_but_should_answer"]] == ["a"] and out["answered_but_should_abstain"] == []
    assert seen == ["a"]


def test_unanswerable_questions_that_were_answered_are_listed():
    out = analyse([(tune("u", "unanswerable"), res(0.9)), (tune("v", "unanswerable"), res(0.1))])
    assert [x["id"] for x in out["answered_but_should_abstain"]] == ["u"]


def test_the_gold_quote_separates_search_failures_from_model_or_verifier_failures():
    pairs = [(tune("found"), res(0.4)), (tune("missed"), res(0.4))]
    out = analyse(pairs, lambda x: x["id"] == "found")
    flags = {x["id"]: x["gold_quote_in_8_passages"] for x in out["abstained_but_should_answer"]}
    assert flags == {"found": True, "missed": False}
    assert out["quote@8"] == {"found": 1, "of": 2}
