import pytest
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
