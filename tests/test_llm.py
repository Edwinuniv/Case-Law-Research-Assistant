import pytest
import json
from app import llm
from openai import APITimeoutError

class Reply:
    def __init__(self, content): self.choices = [type("C", (), {"message": type("M", (), {"content": content})})]

def fake_client(replies):
    calls = []
    class Completions:
        def create(self, **kw):
            calls.append(1)
            r = replies.pop(0)
            if isinstance(r, Exception): raise r
            return Reply(r)
    class Client: chat = type("Chat", (), {"completions": Completions()})()
    return (lambda: Client()), calls

def test_retries_once_on_invalid_json(monkeypatch):          # SR20
    make, calls = fake_client(["not json", '{"status": "NOT_SUPPORTED", "sentences": []}'])
    monkeypatch.setattr(llm, "_client", make)
    assert llm.ask_model("q", {})["status"] == "NOT_SUPPORTED" and len(calls) == 2

def test_gives_up_after_two_invalid_replies(monkeypatch):
    make, calls = fake_client(["bad", "bad again"])
    monkeypatch.setattr(llm, "_client", make)
    with pytest.raises(llm.ModelError):
        llm.ask_model("q", {})

def test_timeout_is_not_retried(monkeypatch):                # SR4
    make, calls = fake_client([APITimeoutError(request=None), "{}"])
    monkeypatch.setattr(llm, "_client", make)
    with pytest.raises(llm.ModelError, match="timeout"):
        llm.ask_model("q", {})
    assert len(calls) == 1


# --- Not in the guide: Groq's free tier refuses calls above 8,000 tokens per minute (see AI_LOG.md) ---
import httpx
from openai import RateLimitError

def rate_limited(seconds, limit="tokens per minute (TPM)"):
    response = httpx.Response(429, headers={"retry-after": seconds}, request=httpx.Request("POST", "http://x"))
    return RateLimitError(f"Rate limit reached for model on {limit}", response=response, body=None)

def test_rate_limit_says_how_long_to_wait(monkeypatch):
    make, calls = fake_client([rate_limited("4"), "{}"])
    monkeypatch.setattr(llm, "_client", make)
    with pytest.raises(llm.ModelError, match="rate limit reached, retry after 4 s"):
        llm.ask_model("q", {})
    assert len(calls) == 1                     # no waiting inside a visitor's request (SR4)

def test_daily_limit_is_named_in_the_error(monkeypatch):     # the evaluation pauses on it (--resume)
    make, _ = fake_client([rate_limited("1320", "tokens per day (TPD)")])
    monkeypatch.setattr(llm, "_client", make)
    with pytest.raises(llm.ModelError, match="rate limit reached per day, retry after 1320 s"):
        llm.ask_model("q", {})



# --- Answer v2 (EVALUATION.md "Answer v2 rule", 2026-11-13): the conversation as messages, prompt caching, tokens ---
def passage(n):
    return {"case_name": f"Case {n} v. State", "date_filed": "2020-01-01", "opinion_label": "Opinion of the Court",
            "section": "", "text": f"Text of passage {n}."}

FIRST = {"question": "Did the Court strike down the law?", "passages": [("P1", passage(1)), ("P2", passage(2))],
         "sentences": [{"text": "The Court struck it down.", "sources": ["P1"], "quote": "Text of passage 1."}]}

def test_an_independent_question_with_the_old_prompt_is_built_exactly_as_before():       # rule (4)
    msgs = llm.build_messages("q", {"P1": passage(1)}, None, "v1")
    assert msgs == [{"role": "system", "content": llm.SYSTEM_PROMPT},
                    {"role": "user", "content": f"PASSAGES:\n\n{llm.format_passages({'P1': passage(1)})}\n\nQUESTION: q"}]

def test_a_follow_up_sends_the_earlier_turn_with_only_the_passages_its_answer_cited():   # part 3 (A): Groq's 413
    turn2 = llm.build_messages("What did the dissent say?", {"P3": passage(3)}, [FIRST], "v2")
    assert turn2[0]["content"] == llm.SYSTEM_PROMPT_V2 and "Did the Court strike down the law?" in turn2[1]["content"]
    assert "Text of passage 1." in turn2[1]["content"] and "Text of passage 2." not in turn2[1]["content"]
    assert turn2[2]["role"] == "assistant" and "The Court struck it down." in turn2[2]["content"]
    assert turn2[-1]["role"] == "user" and "What did the dissent say?" in turn2[-1]["content"]
    assert "Text of passage 3." in turn2[-1]["content"]

def test_a_passage_cited_in_two_turns_is_sent_once():
    again = {"question": "And why?", "passages": [("P1", passage(1)), ("P2", passage(2))],
             "sentences": [{"text": "Because.", "sources": ["P1"], "quote": "Text of passage 1."}]}
    msgs = llm.build_messages("And then?", {}, [FIRST, again], "v2")
    assert json.dumps(msgs).count("Text of passage 1.") == 3       # sent once; quoted in the two answers

def test_the_size_of_a_request_is_estimated_on_the_safe_side():                  # part 3 (B)
    msgs = [{"role": "user", "content": "x" * 3500}, {"role": "assistant", "content": "y" * 3500}]
    assert llm.estimate_tokens(msgs) == 2000                            # 3.5 characters a token (real: about 4.5)

def test_a_follow_up_without_new_passages_sends_only_the_question():                       # reuse, fewer tokens
    msgs = llm.build_messages("And why?", {}, [FIRST], "v2")
    assert "PASSAGES" not in msgs[-1]["content"] and "And why?" in msgs[-1]["content"]

def test_the_new_prompt_forbids_answers_outside_the_law_and_keeps_the_quote_rule():
    assert "OFF_TOPIC" in llm.SYSTEM_PROMPT_V2 and "quote" in llm.SYSTEM_PROMPT_V2
    assert llm.build_messages("q", {}, None, "v2")[0]["content"] == llm.SYSTEM_PROMPT_V2

class UsageReply(Reply):
    def __init__(self, content, prompt, cached, completion):
        super().__init__(content)
        details = type("D", (), {"cached_tokens": cached})()
        self.usage = type("U", (), {"prompt_tokens": prompt, "completion_tokens": completion, "prompt_tokens_details": details})()

def test_the_tokens_of_each_call_are_recorded_with_the_cached_ones(monkeypatch):
    class Completions:
        def create(self, **kw): return UsageReply('{"status": "NOT_SUPPORTED", "sentences": []}', 1200, 1000, 40)
    class Client: chat = type("Chat", (), {"completions": Completions()})()
    monkeypatch.setattr(llm, "_client", lambda: Client())
    llm.ask_model("q", {})
    assert llm.LAST_USAGE == {"input": 1200, "cached": 1000, "output": 40}

def test_a_removed_sentence_is_never_sent_back_to_the_model():
    turn = {**FIRST, "removed": [{"text": "An unverified claim.", "sources": ["P2"], "quote": "x", "problems": ["quote not found"]}]}
    assert "An unverified claim." not in json.dumps(llm.build_messages("And?", {}, [turn], "v2"))

def test_with_two_earlier_turns_each_request_still_starts_like_the_one_before():         # the cache keeps working
    second = {"question": "And the dissent?", "passages": [("P3", passage(3))],
              "sentences": [{"text": "The dissent disagreed.", "sources": ["P3"], "quote": "Text of passage 3."}]}
    turn2 = llm.build_messages(second["question"], dict(second["passages"]), [FIRST], "v2")
    turn3 = llm.build_messages("Why?", {}, [FIRST, second], "v2")
    assert turn3[:len(turn2)] == turn2

def capture_client(seen):
    class Completions:
        def create(self, **kw):
            seen.append(kw)
            return Reply('{"status": "NOT_SUPPORTED", "sentences": []}')
    class Client: chat = type("Chat", (), {"completions": Completions()})()
    return lambda: Client()

def test_v2_asks_for_the_reasoning_effort_of_the_setting_and_v1_sends_none(monkeypatch):    # fewer tokens
    seen = []
    monkeypatch.setattr(llm, "_client", capture_client(seen))
    llm.ask_model("q", {}, None, "v2", reasoning_effort="low")
    llm.ask_model("q", {})                                                                  # v1: as evaluated
    assert seen[0]["reasoning_effort"] == "low" and "reasoning_effort" not in seen[1]


# --- Chat follow-ups, part 2 (EVALUATION.md, 2026-11-13): the user's statement is checked, not agreed with ---
def test_a_follow_up_asks_the_model_to_check_what_the_user_says():               # "so what happened is ...?"
    msgs = llm.build_messages("So he threatened her face to face?", {}, [FIRST], "v2")
    assert llm.FOLLOW_UP_NOTE in msgs[-1]["content"] and "never agree" in llm.FOLLOW_UP_NOTE.lower()
    assert llm.FOLLOW_UP_NOTE not in msgs[1]["content"]                 # the chat's first question is sent as before

def test_an_independent_question_is_sent_without_the_follow_up_note():          # run 4 and eval-v1 unchanged
    assert llm.FOLLOW_UP_NOTE not in json.dumps(llm.build_messages("q", {"P1": passage(1)}, None, "v2"))
