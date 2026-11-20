"""The fallback chain of a cloud provider (decision 0018), with stand-in clients."""

import httpx
import pytest

from app.llm import LLMError, Message, effective_provider, make_client
from app.llm.base import DAILY_LIMIT, ChatTurn, LLMClient, ToolCall
from app.llm.factory import GROQ_MAX_RETRY_WAIT_S, GROQ_RETRIES
from app.llm.fake import DEMO_NOTICE, FakeClient
from app.llm.fallback import FallbackClient, ollama_available, record_switch, switched_to
from app.llm.openai_compat import OpenAICompatClient
from tests.conftest import make_settings


class Scripted(LLMClient):
    def __init__(self, provider: str, turns: list, model: str = "m") -> None:
        self.provider, self.model, self._turns, self.calls = provider, model, list(turns), 0

    def chat(self, messages, tools, *, allow_tools=True):
        self.calls += 1
        step = self._turns.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


LIMIT = LLMError(f"{DAILY_LIMIT} on the Groq API for openai/gpt-oss-120b. Try again in 5m.")


def test_a_daily_limit_moves_the_turn_to_ollama_with_a_note() -> None:
    groq = Scripted("groq", [LIMIT])
    ollama = Scripted(
        "ollama",
        [ChatTurn(tool_calls=(ToolCall("1", "list_families"),)), ChatTurn("Seven families.")],
        "qwen3",
    )
    client = FallbackClient(groq, [("ollama", lambda: ollama), ("fake", FakeClient)])

    first = client.chat([Message("user", "hi")], [])
    second = client.chat([Message("user", "hi")], [])

    assert first.tool_calls and not first.content  # the note waits for text
    assert second.content.startswith("_Groq's free daily quota is used up")
    assert "local Ollama model (qwen3)" in second.content
    assert second.content.endswith("Seven families.")
    assert groq.calls == 1  # not asked again in the same turn


def test_without_ollama_the_turn_falls_back_to_demo_mode() -> None:
    client = FallbackClient(
        Scripted("groq", [LIMIT]), [("ollama", lambda: None), ("fake", FakeClient)]
    )

    answer = client.chat([Message("user", "hi")], []).content

    assert "demo mode until it resets" in answer and "start.cmd ollama" in answer
    assert answer.endswith(DEMO_NOTICE)


def test_other_errors_are_not_hidden() -> None:
    client = FallbackClient(
        Scripted("groq", [LLMError("The Groq API rejected the key.")]), [("fake", FakeClient)]
    )

    with pytest.raises(LLMError, match="rejected the key"):
        client.chat([], [])


def test_no_available_fallback_keeps_the_daily_limit_error() -> None:
    client = FallbackClient(Scripted("groq", [LIMIT]), [("ollama", lambda: None)])

    with pytest.raises(LLMError, match=DAILY_LIMIT):
        client.chat([], [])


def test_without_a_key_the_factory_uses_the_first_available_fallback(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    settings = make_settings(tmp_path, llm_provider="groq", groq_api_key=None, llm_fallback="fake")
    assert make_client(settings).provider == "fake"

    with pytest.raises(LLMError, match="GROQ_API_KEY"):
        make_client(
            make_settings(tmp_path, llm_provider="groq", groq_api_key=None, llm_fallback="")
        )


def test_with_a_key_the_factory_wraps_the_cloud_provider(tmp_path) -> None:
    settings = make_settings(
        tmp_path, llm_provider="groq", groq_api_key="k", llm_fallback="ollama,fake"
    )
    client = make_client(settings)
    assert isinstance(client, FallbackClient) and client.provider == "groq"
    client.close()
    plain = make_client(make_settings(tmp_path, llm_provider="ollama", llm_fallback="fake"))
    assert not isinstance(plain, FallbackClient)  # a local provider has no fallback
    plain.close()


@pytest.mark.parametrize(
    ("pulled", "model", "expected"),
    [
        (["qwen3:4b-instruct-2507-q4_K_M"], "qwen3:4b-instruct-2507", True),
        (["llama3:latest"], "llama3", True),
        (["qwen3:4b-instruct-2507-q4_K_M"], "llama3", False),
        ([], "qwen3", False),
    ],
)
def test_ollama_counts_only_with_the_model_pulled(pulled, model, expected) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": [{"name": n} for n in pulled]})

    assert ollama_available("http://o", model, transport=httpx.MockTransport(handler)) is expected


def test_ollama_down_is_not_available() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    assert ollama_available("http://o", "qwen3", transport=httpx.MockTransport(handler)) is False


def test_after_a_daily_limit_later_clients_stay_switched(tmp_path) -> None:
    fake_first = FallbackClient(Scripted("groq", [LIMIT]), [("fake", FakeClient)])
    fake_first.chat([Message("user", "hi")], [])
    assert switched_to() == "fake"

    settings = make_settings(tmp_path, llm_provider="groq", groq_api_key="k", llm_fallback="fake")
    client = make_client(settings)  # the next turn does not ask Groq again
    assert isinstance(client, FakeClient)
    assert DAILY_LIMIT not in client.chat([Message("user", "hi")], []).content
    assert effective_provider(settings) == "fake"


def test_the_first_switch_is_kept() -> None:
    record_switch("ollama")
    record_switch("fake")
    assert switched_to() == "ollama"


def test_other_errors_do_not_switch() -> None:
    client = FallbackClient(
        Scripted("groq", [LLMError("Groq API error 500 for m: boom")]), [("fake", FakeClient)]
    )
    with pytest.raises(LLMError):
        client.chat([], [])
    assert switched_to() is None


def test_a_per_minute_limit_is_waited_out_and_a_daily_one_is_not(tmp_path) -> None:
    replies = [
        httpx.Response(429, headers={"retry-after": "45"}, json={"error": {"message": "TPM"}}),
        httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]}),
        httpx.Response(429, headers={"x-ratelimit-reset-tokens": "3h"}, json={}),
    ]
    waits: list[float] = []
    client = OpenAICompatClient(
        "k",
        "m",
        provider="groq",
        max_retry_wait=GROQ_MAX_RETRY_WAIT_S,
        retries=GROQ_RETRIES,
        transport=httpx.MockTransport(lambda request: replies.pop(0)),
        sleep=waits.append,
    )
    assert client.chat([], []).content == "ok"
    with pytest.raises(LLMError, match=DAILY_LIMIT):
        client.chat([], [])
    assert waits == [45.0] and GROQ_MAX_RETRY_WAIT_S == 60
