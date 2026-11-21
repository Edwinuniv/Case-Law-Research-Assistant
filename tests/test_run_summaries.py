"""scripts/run_summaries.py (EVALUATION.md "Passage summaries", 2026-11-21), written before the script: each request of
summaries-v1 after its first question answered as on the website, the four conditions, pause and resume.
Fake search, model and checker: no database, no Groq."""
import json
import pytest
from app import llm
from app.config import DEFAULT_SETTINGS
from scripts import run_summaries as run
from tests.test_citations import INDEX
from tests.test_passage_summaries import OneSearch

ITEM = {"id": "S001", "first_id": "A035", "first": "Is the President immune?", "request": "summarize the first passage",
        "kind": "passage", "split": "tune"}
S = dict(DEFAULT_SETTINGS, **run.SETTINGS_FOR_RUN)     # as the run: the defaults + the rule's settings


@pytest.fixture
def models(monkeypatch):
    calls = []

    def write(question, passages, *a, **k):
        calls.append(("answer", question))
        return {"status": "SUPPORTED", "sentences": [{"text": "The President has absolute immunity for conclusive and "
                                                              "preclusive actions.", "sources": ["P1"],
                                                      "quote": "enjoys absolute immunity for actions within his conclusive"}]}

    def pick(request, passages, *a, **k):
        calls.append(("pick", sorted(passages)))
        return {"picks": [{"passage": pid, "sentence": " ".join(p["text"].split()[:8])} for pid, p in passages.items()]}
    monkeypatch.setattr(llm, "ask_model", write)
    monkeypatch.setattr(llm, "pick_sentences", pick)
    return calls


def no_citations(r, q, index):
    return [[] for _ in r["sentences"]], 0


def test_the_first_question_is_answered_then_the_request_uses_that_answer(models):
    row = run.run_one(ITEM, OneSearch(), INDEX, S, checker=no_citations, log=lambda m: None)
    assert models[0] == ("answer", "Is the President immune?") and models[1] == ("pick", ["P1"])
    assert row["id"] == "S001" and row["status"] == "ANSWERED" and row["first_status"] in ("ANSWERED", "LOW_CONFIDENCE")
    assert row["sent"][0]["label"] == "Opinion of the Court (Roberts)" and row["sent"][0]["pid"] == "P1"
    assert row["shown"][0]["text"].startswith("Opinion of the Court (Roberts): “") and row["shown"][0]["sources"] == ["P1"]


def rows(n_shown, false=0, outside=0):
    """n_shown requests shown, the rest NOT_SUPPORTED; `false` false citations; `outside` sentences citing a passage not sent."""
    out = []
    for i in range(14):
        shown = i < n_shown
        sources = ["P9"] if i < outside else ["P1"]
        out.append({"id": f"S{i + 1:03}", "status": "ANSWERED" if shown else "NOT_SUPPORTED",
                    "sent": [{"pid": "P1"}], "shown": [{"text": "x", "sources": sources}] if shown else [],
                    "false_citations": false if i == 0 else 0, "citations_shown": 1})
    return out


def test_all_conditions_hold_with_twelve_shown_and_no_false_citation():
    v = run.verdict(rows(12))
    assert v["shown"] == 12 and v["false_citations"] == 0 and v["only_requested"] == 1.0 and v["automatic_conditions_hold"]


@pytest.mark.parametrize("bad", [dict(n_shown=11), dict(n_shown=14, false=1), dict(n_shown=14, outside=1)])
def test_eleven_shown_a_false_citation_or_a_passage_not_sent_fails(bad):
    assert not run.verdict(rows(**bad))["automatic_conditions_hold"]


def test_an_error_is_not_shown():
    r = rows(14)
    r[0]["status"] = "ERROR"
    assert run.verdict(r)["shown"] == 13


def test_resume_skips_the_requests_already_done(models, tmp_path):
    path = tmp_path / "run.json"
    path.write_text(json.dumps({"settings": S, "rows": [{"id": "S001"}]}))
    done = []
    run.run_all([ITEM, {**ITEM, "id": "S002"}], OneSearch(), INDEX, path, checker=no_citations,
                log=lambda m: None, on_row=lambda row: done.append(row["id"]))
    assert done == ["S002"] and [r["id"] for r in json.loads(path.read_text())["rows"]] == ["S001", "S002"]


def test_the_daily_limit_pauses_the_run_and_keeps_what_is_done(monkeypatch, tmp_path):
    def day(*a, **k):
        raise llm.ModelError("rate limit reached per day, retry after 3000 s")
    monkeypatch.setattr(llm, "ask_model", day)
    path = tmp_path / "run.json"
    with pytest.raises(run.DailyLimit):
        run.run_all([ITEM], OneSearch(), INDEX, path, S, checker=no_citations, log=lambda m: None)
    assert json.loads(path.read_text())["rows"] == []


def test_the_run_uses_the_rules_settings():
    assert S["passage_summaries"] is True and S["prompt_version"] == "v2" and S["tau_abstain"] == 0.20


def test_the_passages_search_scores_are_saved_so_a_run_can_be_rechecked(models):
    row = run.run_one(ITEM, OneSearch(), INDEX, S, checker=no_citations, log=lambda m: None)
    assert row["sent"][0]["score"] == 0.9                           # run 1 could not be rechecked without them


def test_run_6_is_a_new_file():
    assert run.RUN.name == "summaries_run6.json"
