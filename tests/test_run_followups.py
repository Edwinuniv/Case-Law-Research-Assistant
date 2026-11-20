"""Measuring the follow-up pairs (followups-v1), written from the "Follow-up questions rule" of EVALUATION.md before
the code. No model: evaluate.answer_with_retry is replaced by a fake that records how it was called. TEST database."""
import json
import pytest
from app import evaluate
from scripts import run_followups as rf

S = {"tau_abstain": 0.2, "tau_confident": 0.6, "min_retrieval": 0.3}
P1 = {"decision_id": 1, "opinion_id": 1, "text": "The Court held X.", "score": 0.9}


def pair(pid, tag="answerable", split="tune", **extra):
    return {"id": pid, "tag": tag, "kind": "explain", "split": split, "author": "Edwin",
            "first_question": f"first {pid}?", "follow_up": f"follow {pid}?", "expected_answer": "",
            "gold_decision_ids": [1], "gold_quote": "", "must_not_appear": [], "why": "", **extra}


def answer(question, status="ANSWERED", text="The Court held X.", support=0.9):
    sentences = [{"text": text, "sources": ["P1"], "groundedness": 1.0}] if status != "NOT_SUPPORTED" else []
    return {"question": question, "status": status, "top_score": 0.9, "support_score": support,
            "model_said": "SUPPORTED" if status != "NOT_SUPPORTED" else "NOT_SUPPORTED", "reason": "",
            "sentences": sentences, "shown_sentences": sentences, "removed": [], "fabrications_caught": 0,
            "passages": [("P1", P1)], "retrieved_decisions": [1], "ms_total": 10, "tokens": {}}


@pytest.fixture
def fake(monkeypatch, clean_db):
    """calls: (question, history) in order; replies: question -> the answer to give (default ANSWERED)."""
    calls, replies = [], {}

    def ask(question, searcher, index, settings, log, history=None):
        calls.append((question, history))
        reply = replies.get(question, answer(question))
        if isinstance(reply, Exception):
            raise reply
        return reply
    monkeypatch.setattr(evaluate, "answer_with_retry", ask)
    return calls, replies


def run(pairs, out, **kw):
    return rf.run(pairs, None, None, S, out, judge=False, log=lambda *a: None, **kw)


def test_the_follow_up_is_asked_after_the_first_question_with_its_answer_as_history(fake, tmp_path):
    calls, _ = fake
    run([pair("F001")], tmp_path / "r.json")
    (q1, h1), (q2, h2) = calls
    assert (q1, h1) == ("first F001?", None)                       # the first question: on its own
    assert q2 == "follow F001?" and len(h2) == 1                   # the follow-up: with the chat so far
    assert h2[0]["question"] == "first F001?" and h2[0]["passages"] == [("P1", P1)]


def test_only_the_chosen_split_is_measured(tmp_path):
    pairs = [pair("F001", split="test"), pair("F002"), pair("F003", tag="adversarial", split="test")]
    assert [p["id"] for p in rf.select(pairs, "tune")] == ["F002"]  # no adversarial TEST pair while deciding
    assert [p["id"] for p in rf.select(pairs, "test")] == ["F001", "F003"]


def test_each_pair_is_saved_with_the_follow_ups_result_and_the_first_status(fake, tmp_path):
    _, replies = fake
    replies["first F002?"] = answer("first F002?", "LOW_CONFIDENCE", support=0.4)
    replies["follow F002?"] = answer("follow F002?", "NOT_SUPPORTED")
    out = tmp_path / "r.json"
    assert run([pair("F002", tag="unanswerable")], out) == "done"
    saved = json.loads(out.read_text())
    row = saved["pairs"]["F002"]
    assert saved["status"] == "done" and saved["settings"] == S
    assert row["first_status"] == "LOW_CONFIDENCE" and row["status_raw"] == "NOT_SUPPORTED" and row["n_kept"] == 0


def test_forbidden_text_shown_is_counted_apart_from_false_citations(fake, tmp_path):
    _, replies = fake
    replies["follow F005?"] = answer("follow F005?", text="United States v. Clinton held that he was immune.")
    out = tmp_path / "r.json"
    run([pair("F005", tag="adversarial", must_not_appear=["United States v. Clinton held"])], out)
    pairs = rf.load(out)
    assert rf.forbidden_shown(pairs, S) == 1
    m = rf.measures(pairs, S)
    assert m["forbidden_text_shown"] == 1 and m["false_citations_shown"] == 0


def test_forbidden_text_in_a_follow_up_that_is_not_shown_does_not_count(fake, tmp_path):
    _, replies = fake
    replies["follow F005?"] = answer("follow F005?", text="United States v. Clinton held it.", support=0.05)
    out = tmp_path / "r.json"                                      # support below tau_abstain: NOT_SUPPORTED
    run([pair("F005", tag="adversarial", must_not_appear=["United States v. Clinton held"])], out)
    assert rf.forbidden_shown(rf.load(out), S) == 0


def test_a_failed_first_answer_is_not_replaced_by_an_independent_question(fake, tmp_path):
    calls, replies = fake
    replies["first F001?"] = answer("first F001?", "ERROR")
    out = tmp_path / "r.json"
    run([pair("F001")], out)
    assert [q for q, _ in calls] == ["first F001?"]                # the follow-up is not asked without its chat
    assert json.loads(out.read_text())["pairs"]["F001"]["status_raw"] == "ERROR"


def test_the_daily_limit_pauses_and_resume_skips_the_pairs_done(fake, tmp_path):
    calls, replies = fake
    replies["first F002?"] = evaluate.DailyLimit("rate limit reached per day")
    out = tmp_path / "r.json"
    assert run([pair("F001"), pair("F002")], out) == "paused"
    saved = json.loads(out.read_text())
    assert list(saved["pairs"]) == ["F001"] and saved["status"] == "paused"   # F002 is asked again, from the start
    del replies["first F002?"]
    calls.clear()
    assert run([pair("F001"), pair("F002")], out, resume=True) == "done"
    assert [q for q, _ in calls] == ["first F002?", "follow F002?"]


def test_resume_refuses_changed_settings(fake, tmp_path):
    out = tmp_path / "r.json"
    run([pair("F001")], out)
    with pytest.raises(ValueError, match="settings changed"):
        rf.run([pair("F001")], None, None, dict(S, tau_abstain=0.5), out, judge=False, log=lambda *a: None, resume=True)


@pytest.mark.parametrize("change, on", [({}, True), ({"false_citations_shown": 1}, False),
                                        ({"forbidden_text_shown": 1}, False),
                                        ({"abstention_precision": 0.75}, False), ({"abstention_recall": None}, False)])
def test_the_switch_goes_on_only_if_every_condition_holds(change, on):
    m = {"false_citations_shown": 0, "forbidden_text_shown": 0, "abstention_precision": 0.8,
         "abstention_recall": 1.0, **change}
    v = rf.verdict(m)
    assert v["switch_on"] is on
    if not on and "abstention" in next(iter(change)):
        assert "report" in v["note"]                               # only (3) failed: off, numbers reported
