import asyncio

import pytest

from backend.src.llm import client as client_module


def test_fast_model_is_provider_compatible() -> None:
    deepseek = client_module.LLMClient(
        api_key="sk-test", base_url="https://api.deepseek.com/v1", model="deepseek-v4-pro"
    )
    openai = client_module.LLMClient(
        api_key="sk-test", base_url="https://api.openai.com/v1", model="gpt-4.1-mini"
    )

    assert deepseek.fast_model() == client_module.FAST_MODEL
    assert openai.fast_model() == "gpt-4.1-mini"


class _Delta:
    reasoning_content = None
    content = "x"


class _Chunk:
    choices = [type("Choice", (), {"delta": _Delta()})()]


class _FakeStream:
    def __init__(self, tracker: dict[str, int]):
        self.tracker = tracker
        self.sent = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.sent:
            raise StopAsyncIteration
        self.sent = True
        self.tracker["active"] += 1
        self.tracker["max"] = max(self.tracker["max"], self.tracker["active"])
        await asyncio.sleep(0.02)
        self.tracker["active"] -= 1
        return _Chunk()


class _Completions:
    def __init__(self, tracker: dict[str, int]):
        self.tracker = tracker

    async def create(self, **kwargs):
        return _FakeStream(self.tracker)


@pytest.mark.asyncio
async def test_stream_semaphore_covers_response_iteration(monkeypatch) -> None:
    tracker = {"active": 0, "max": 0}
    llm = client_module.LLMClient(api_key="sk-test")
    llm._client = type(
        "FakeClient",
        (),
        {"chat": type("Chat", (), {"completions": _Completions(tracker)})()},
    )()
    monkeypatch.setattr(client_module, "_LLM_SEMAPHORE", asyncio.Semaphore(1))

    async def collect():
        return [chunk async for chunk in llm.stream([{"role": "user", "content": "hi"}])]

    await asyncio.gather(collect(), collect())

    assert tracker["max"] == 1
