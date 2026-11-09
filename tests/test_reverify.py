"""Step 8.2: run 2's saved sentences checked again by the changed verifier (EVALUATION.md, quote matching rule).
Same drafts, same passages found again by the same search; the model is asked nothing except the judge for a
sentence that is newly kept. Written from the expected behaviour, before the code."""
from app.config import DEFAULT_SETTINGS
from tests.test_citations import INDEX

S = dict(DEFAULT_SETTINGS)
TEXT = "Held: the Fourteenth Amendment requires a State to license a mar- riage between two people of the same sex."
PASSAGE = {"chunk_id": "1-0", "decision_id": 1, "opinion_id": 1, "case_name": "Obergefell v. Hodges",
           "score": 0.9, "text": TEXT}
QUOTE = "requires a State to license a marriage between two people"          # failed before the fix
BROKEN = {"text": "The Court held that a State must license the marriage.", "sources": ["P1"], "quote": QUOTE,
          "problems": ["quote not found in the cited passage"]}
INVENTED = {**BROKEN, "text": "In Zorblax v. Quimby, the Court held that a State must license it.",
            "problems": ["quote not found in the cited passage", "case name not in our corpus or the cited passage: Zorblax v. Quimby"]}
KEPT = {"text": "The Court held that a State must license a marriage between two people.", "sources": ["P1"],
        "groundedness": 0.9}


def q(i, split="tune"):
    return {"id": i, "tag": "answerable", "split": split, "question": "?", "gold_decision_ids": [1], "must_not_appear": []}


def res(kept=(), removed=(), ranked=(1,), judgements=None):
    return {"status_raw": "ANSWERED" if kept else "NOT_SUPPORTED", "model_said": "SUPPORTED", "top_score": 0.9,
            "support_score": 0.5 if kept else 0.0, "n_kept": len(kept), "n_removed": len(removed),
            "ranked_decisions": list(ranked), "sentences": list(kept), "removed": list(removed),
            "judgements": judgements if judgements is not None else ["yes"] * len(kept), "fabrications_caught": 0,
            "false_by_sentence": [[] for _ in kept], "citations_shown": len(kept), "reason": "", "ms_total": 1}


def reverify(pairs, passages=(PASSAGE,), judged=None):
    from scripts import reverify_run
    calls = [] if judged is None else judged
    def judge(statement, text):
        calls.append(statement)
        return "yes"
    def shown(r, q, index):
        return [[] for _ in r["sentences"]], len(r["sentences"])
    return reverify_run.reverify(pairs, S, lambda question: (list(passages), list(passages)), INDEX, judge, shown)


def test_a_quote_the_fix_now_finds_is_kept_judged_and_scored():
    judged = []
    out = reverify([(q("a"), res(removed=[BROKEN]))], judged=judged)
    (_, r), = out["pairs"]
    assert r["n_kept"] == 1 and r["n_removed"] == 0 and r["support_score"] > 0
    assert judged == [BROKEN["text"]] and r["judgements"] == ["yes"]
    assert out["newly_kept"] == [{"id": "a", "text": BROKEN["text"], "quote": QUOTE, "passage": TEXT}]   # rule (2): checked by hand


def test_a_sentence_removed_for_another_reason_stays_removed():                  # rule (4)
    out = reverify([(q("a"), res(removed=[INVENTED]))])
    (_, r), = out["pairs"]
    assert r["n_kept"] == 0 and out["newly_kept"] == [] and out["kept_despite_other_problem"] == []
    assert any(p.startswith("case name") for p in r["removed"][0]["problems"])


def test_a_kept_sentence_stays_kept_without_asking_the_judge_again():
    judged = []
    out = reverify([(q("a"), res(kept=[KEPT], judgements=["no"]))], judged=judged)
    (_, r), = out["pairs"]
    assert r["n_kept"] == 1 and r["judgements"] == ["no"] and judged == []


def test_a_question_whose_search_changed_is_not_rechecked():                    # rule (1)
    old = res(removed=[BROKEN], ranked=(2,))                                     # run 2 had decision 2 first
    out = reverify([(q("a"), old)])
    assert out["pairs"] == [(q("a"), old)] and out["search_changed"] == ["a"]


def test_every_split_is_rechecked_but_only_tune_is_listed():                    # TEST is reported once, later
    out = reverify([(q("t", "test"), res(removed=[BROKEN])), (q("a"), res(removed=[BROKEN]))])
    assert [r["n_kept"] for _, r in out["pairs"]] == [1, 1]
    assert [x["id"] for x in out["newly_kept"]] == ["a"]


def test_a_quote_the_fix_still_does_not_find_stays_removed():                  # A029: words left out with "..."
    gap = {**BROKEN, "quote": "requires a State ... between two people of the same sex"}
    out = reverify([(q("a"), res(removed=[gap]))])
    (_, r), = out["pairs"]
    assert r["n_kept"] == 0 and out["newly_kept"] == [] and "quote not found in the cited passage" in r["removed"][0]["problems"]


def test_only_the_8_passages_sent_to_the_model_must_be_the_same():              # A027: passages 9-20 tie and swap
    from scripts import reverify_run
    other = {**PASSAGE, "chunk_id": "2-0", "decision_id": 2, "score": 0.5}
    third = {**PASSAGE, "chunk_id": "3-0", "decision_id": 3, "score": 0.5}
    old = res(removed=[BROKEN], ranked=(1, 2, 3))                               # run 2: 2 then 3 after the 8
    out = reverify_run.reverify([(q("a"), old)], S, lambda question: ([PASSAGE], [PASSAGE, third, other]), INDEX,
                                lambda t, p: "yes", lambda r, q, i: ([[] for _ in r["sentences"]], len(r["sentences"])))
    assert out["search_changed"] == [] and out["pairs"][0][1]["n_kept"] == 1
