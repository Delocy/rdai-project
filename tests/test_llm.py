from types import SimpleNamespace

import httpx
import openai
import pytest

from app import llm
from app.config import settings

MESSAGES = [{"role": "user", "content": "hi"}]


@pytest.fixture(autouse=True)
def no_cooldowns(monkeypatch):
    monkeypatch.setattr(llm, "_cooling", {})


def http_error(kind, status: int) -> Exception:
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    return kind("upstream said no", response=httpx.Response(status, request=request), body=None)


class FakeModel:
    """Stands in for an OpenAI-compatible client; records each request's arguments."""

    def __init__(self, reply: str | None = "{}", error: Exception | None = None):
        self.requests = []
        self.reply, self.error = reply, error
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.reply))])


def test_completions_ask_for_deterministic_output(monkeypatch):
    model = FakeModel()
    monkeypatch.setattr(llm, "_attempts", lambda kind: [(model, "some-model")])
    llm.complete([{"role": "user", "content": "hi"}], llm.TEXT)
    assert model.requests[0]["temperature"] == 0


def test_a_failing_model_falls_through_to_the_next(monkeypatch):
    broken, working = FakeModel(error=RuntimeError("rate limited")), FakeModel(reply="ok")
    monkeypatch.setattr(llm, "_attempts", lambda kind: [(broken, "first"), (working, "second")])
    assert llm.complete([{"role": "user", "content": "hi"}], llm.TEXT) == "ok"


def test_no_model_left_raises_so_the_agent_can_degrade(monkeypatch):
    monkeypatch.setattr(llm, "_attempts", lambda kind: [(FakeModel(error=RuntimeError("down")), "only")])
    with pytest.raises(RuntimeError, match="no text model available"):
        llm.complete([{"role": "user", "content": "hi"}], llm.TEXT)


def test_a_rate_limited_model_is_skipped_for_a_while(monkeypatch):
    limited, working = FakeModel(error=http_error(openai.RateLimitError, 429)), FakeModel(reply="ok")
    monkeypatch.setattr(llm, "_attempts", lambda kind: [(limited, "limited"), (working, "working")])
    llm.complete(MESSAGES, llm.TEXT)
    llm.complete(MESSAGES, llm.TEXT)
    assert (len(limited.requests), len(working.requests)) == (1, 2)


def test_a_model_that_no_longer_exists_is_skipped_for_a_while(monkeypatch):
    gone, working = FakeModel(error=http_error(openai.NotFoundError, 404)), FakeModel(reply="ok")
    monkeypatch.setattr(llm, "_attempts", lambda kind: [(gone, "gone"), (working, "working")])
    llm.complete(MESSAGES, llm.TEXT)
    llm.complete(MESSAGES, llm.TEXT)
    assert len(gone.requests) == 1


def test_a_skipped_model_is_tried_again_once_the_cooldown_ends(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(llm.time, "monotonic", lambda: clock[0])
    limited, working = FakeModel(error=http_error(openai.RateLimitError, 429)), FakeModel(reply="ok")
    monkeypatch.setattr(llm, "_attempts", lambda kind: [(limited, "limited"), (working, "working")])
    llm.complete(MESSAGES, llm.TEXT)
    clock[0] += llm.COOLDOWN_SECONDS + 1
    llm.complete(MESSAGES, llm.TEXT)
    assert len(limited.requests) == 2


def test_a_one_off_failure_is_retried_on_the_next_search(monkeypatch):
    flaky, working = FakeModel(error=RuntimeError("bad gateway")), FakeModel(reply="ok")
    monkeypatch.setattr(llm, "_attempts", lambda kind: [(flaky, "flaky"), (working, "working")])
    llm.complete(MESSAGES, llm.TEXT)
    llm.complete(MESSAGES, llm.TEXT)
    assert len(flaky.requests) == 2


def test_configured_says_whether_any_model_is_set_up(monkeypatch):
    for name in ("openrouter_api_key", "ollama_text_model", "ollama_vision_model"):
        monkeypatch.setattr(settings(), name, "")
    assert not llm.configured(llm.TEXT)
    monkeypatch.setattr(settings(), "ollama_text_model", "qwen2.5:7b")
    assert llm.configured(llm.TEXT)
    assert not llm.configured(llm.VISION)
