from app.evaluate import status_at, metrics
from app.config import DEFAULT_SETTINGS

S = dict(DEFAULT_SETTINGS)

def res(support, top=0.8, said="SUPPORTED", kept=1, ranked=(1,), false=()):
    return {"status_raw": "ANSWERED", "top_score": top, "model_said": said, "support_score": support,
            "n_kept": kept, "ranked_decisions": list(ranked), "false_by_sentence": [list(false)] * kept,
            "citations_shown": kept, "fabrications_caught": 0, "judgements": ["yes"] * kept,
            "sentences": [{"groundedness": 1.0}] * kept, "ms_total": 100}

def q(i, tag, gold=(1,)):
    return {"id": i, "tag": tag, "split": "test", "question": "?", "gold_decision_ids": list(gold), "must_not_appear": []}

def test_status_follows_thresholds():
    assert status_at(res(0.9), S) == "ANSWERED"
    assert status_at(res(0.6), S) == "LOW_CONFIDENCE"
    assert status_at(res(0.3), S) == "NOT_SUPPORTED"
    assert status_at(res(0.9, top=0.1), S) == "NOT_SUPPORTED"

def test_abstention_precision_and_recall():
    pairs = [(q("a", "answerable"), res(0.9)), (q("b", "unanswerable"), res(0.2)),
             (q("c", "unanswerable"), res(0.9)), (q("d", "answerable"), res(0.2))]
    m = metrics(pairs, S)
    assert m["abstention_precision"] == 0.5 and m["abstention_recall"] == 0.5

def test_false_citations_count_only_when_shown():
    pairs = [(q("a", "adversarial"), res(0.9, false=("x",))), (q("b", "adversarial"), res(0.1, false=("y",)))]
    assert metrics(pairs, S)["false_citations_shown"] == 1

def test_recall_at_k():
    pairs = [(q("a", "answerable", gold=(5,)), res(0.9, ranked=(1, 2, 5)))]
    m = metrics(pairs, S)
    assert m["recall@1"] == 0 and m["recall@5"] == 1 and round(m["mrr@10"], 2) == 0.33
