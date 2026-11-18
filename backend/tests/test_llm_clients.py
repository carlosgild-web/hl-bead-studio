"""The three LLM clients, with mocked transports (no Ollama, key or network)."""

import json

import httpx
import pytest

from app.llm import LLMError, Message, ToolCall, ToolSpec, make_client
from app.llm.anthropic import API_VERSION, AnthropicClient, from_anthropic, to_anthropic
from app.llm.fake import DEMO_NOTICE, FakeClient, FakeScriptExhausted, call, last_result, say
from app.llm.ollama import OllamaClient
from tests.conftest import make_settings

TOOLS = [ToolSpec("list_families", "List the families", {"type": "object", "properties": {}})]


def _mock(handler) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


# --- Fake ----------------------------------------------------------------------------


def test_fake_follows_its_script_and_then_raises():
    client = FakeClient([call("list_families"), say("Seven families.")])
    first = client.chat([Message("user", "hi")], TOOLS)
    assert first.tool_calls[0].name == "list_families"
    assert client.chat([], TOOLS).content == "Seven families."
    with pytest.raises(FakeScriptExhausted):
        client.chat([], TOOLS)


def test_fake_without_script_is_demo_mode():
    assert FakeClient().chat([Message("user", "hi")], TOOLS).content == DEMO_NOTICE


def test_fake_step_can_react_to_tool_results():
    messages = [Message("tool", json.dumps({"ok": True}), tool_call_id="1", name="x")]
    client = FakeClient([lambda m, t: say(f"ok={last_result(m, 'x')['ok']}")])
    assert client.chat(messages, TOOLS).content == "ok=True"


# --- Ollama --------------------------------------------------------------------------


def test_ollama_sends_native_tools_and_reads_tool_calls():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": "<think>hmm</think>",
                    "tool_calls": [{"function": {"name": "list_families", "arguments": {}}}],
                },
                "prompt_eval_count": 10,
                "eval_count": 3,
            },
        )

    client = OllamaClient("http://ollama", "qwen", transport=_mock(handler))
    turn = client.chat([Message("user", "families?")], TOOLS)
    assert seen["tools"][0]["function"]["name"] == "list_families"
    assert seen["options"]["temperature"] == 0
    assert turn.tool_calls[0].name == "list_families"
    assert turn.content == ""
    assert (turn.prompt_tokens, turn.completion_tokens) == (10, 3)


@pytest.mark.parametrize(
    "text",
    [
        '<tool_call>{"name": "list_families", "arguments": {}}</tool_call>',
        '```json\n{"name": "list_families", "arguments": {}}\n```',
        '{"name": "list_families", "arguments": {}}',
    ],
)
def test_ollama_recovers_tool_calls_written_as_text(text):
    def handler(request):
        return httpx.Response(200, json={"message": {"content": text}})

    turn = OllamaClient("http://o", "m", transport=_mock(handler)).chat([], TOOLS)
    assert [c.name for c in turn.tool_calls] == ["list_families"]


def test_ollama_ignores_json_naming_an_unknown_tool():
    def handler(request):
        return httpx.Response(200, json={"message": {"content": '{"name": "rm", "x": 1}'}})

    turn = OllamaClient("http://o", "m", transport=_mock(handler)).chat([], TOOLS)
    assert turn.tool_calls == ()


def test_ollama_missing_model_says_how_to_pull_it():
    def handler(request):
        return httpx.Response(404, json={"error": "model 'qwen' not found"})

    with pytest.raises(LLMError, match="ollama pull qwen"):
        OllamaClient("http://o", "qwen", transport=_mock(handler)).chat([], TOOLS)


def test_ollama_unreachable():
    def handler(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(LLMError, match="not reachable"):
        OllamaClient("http://o", "m", transport=_mock(handler)).chat([], TOOLS)


# --- Anthropic -----------------------------------------------------------------------


def _anthropic_reply(content, stop="end_turn", **extra):
    return {
        "content": content,
        "stop_reason": stop,
        "usage": {"input_tokens": 5, "cache_read_input_tokens": 100, "output_tokens": 7},
        **extra,
    }


def test_anthropic_request_shape():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["headers"] = request.headers
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_anthropic_reply([{"type": "text", "text": "Hi"}]))

    client = AnthropicClient("k", "claude-sonnet-5-5", transport=_mock(handler))
    turn = client.chat([Message("system", "Be a guide."), Message("user", "hello")], TOOLS)
    body = seen["body"]
    assert seen["headers"]["x-api-key"] == "k"
    assert seen["headers"]["anthropic-version"] == API_VERSION
    assert body["system"] == "Be a guide."
    assert body["messages"] == [{"role": "user", "content": [{"type": "text", "text": "hello"}]}]
    assert body["tools"][0]["input_schema"] == {"type": "object", "properties": {}}
    assert "temperature" not in body
    assert body["fallbacks"] == "default"
    assert turn.content == "Hi"
    assert turn.prompt_tokens == 105 and turn.completion_tokens == 7


def test_anthropic_replays_assistant_blocks_and_merges_tool_results():
    thinking = {"type": "thinking", "thinking": "", "signature": "sig"}
    use = {"type": "tool_use", "id": "t1", "name": "list_families", "input": {}}
    use2 = {"type": "tool_use", "id": "t2", "name": "list_families", "input": {}}
    turn = from_anthropic(_anthropic_reply([thinking, use, use2], stop="tool_use"))
    assert [c.id for c in turn.tool_calls] == ["t1", "t2"]

    messages = [
        Message("user", "go"),
        Message("assistant", "", turn.tool_calls, provider_content=turn.provider_content),
        Message("tool", '{"a": 1}', tool_call_id="t1", name="list_families"),
        Message("tool", '{"error": 1}', tool_call_id="t2", name="list_families", is_error=True),
    ]
    _, converted = to_anthropic(messages)
    assert converted[1] == {"role": "assistant", "content": [thinking, use, use2]}
    results = converted[2]["content"]
    assert converted[2]["role"] == "user" and len(converted) == 3
    assert [b["tool_use_id"] for b in results] == ["t1", "t2"]
    assert results[1]["is_error"] is True


def test_anthropic_builds_blocks_for_turns_of_other_providers():
    m = Message("assistant", "Checking.", (ToolCall("x1", "list_families", {}),))
    _, converted = to_anthropic([Message("user", "go"), m])
    assert converted[1]["content"] == [
        {"type": "text", "text": "Checking."},
        {"type": "tool_use", "id": "x1", "name": "list_families", "input": {}},
    ]


def test_anthropic_refusal_is_an_error():
    data = _anthropic_reply([], stop="refusal", stop_details={"category": "cyber"})
    with pytest.raises(LLMError, match="declined.*cyber"):
        from_anthropic(data)


def test_anthropic_retries_busy_then_succeeds():
    replies = iter(
        [
            httpx.Response(529, headers={"retry-after": "1"}, json={"error": {}}),
            httpx.Response(200, json=_anthropic_reply([{"type": "text", "text": "ok"}])),
        ]
    )
    waits = []
    client = AnthropicClient("k", "m", transport=_mock(lambda r: next(replies)), sleep=waits.append)
    assert client.chat([Message("user", "x")], []).content == "ok"
    assert waits == [1.0]


def test_anthropic_bad_key_message():
    def handler(request):
        return httpx.Response(401, json={"error": {"type": "authentication_error"}})

    with pytest.raises(LLMError, match="ANTHROPIC_API_KEY"):
        AnthropicClient("k", "m", transport=_mock(handler)).chat([], [])


# --- factory -------------------------------------------------------------------------


def test_factory_defaults_to_fake(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert make_client(make_settings(tmp_path)).provider == "fake"


def test_factory_anthropic_without_key_explains(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    settings = make_settings(tmp_path, llm_provider="anthropic")
    with pytest.raises(LLMError, match="ANTHROPIC_API_KEY"):
        make_client(settings)


def test_factory_ollama(tmp_path):
    client = make_client(make_settings(tmp_path, llm_provider="ollama", ollama_model="q"))
    assert (client.provider, client.model) == ("ollama", "q")
    client.close()


def test_last_call_keeps_the_tools_but_turns_them_off():
    seen = {}

    def anthropic(request):
        seen["anthropic"] = json.loads(request.content)
        return httpx.Response(200, json=_anthropic_reply([{"type": "text", "text": "ok"}]))

    def ollama(request):
        seen["ollama"] = json.loads(request.content)
        return httpx.Response(200, json={"message": {"content": "ok"}})

    AnthropicClient("k", "m", transport=_mock(anthropic)).chat([], TOOLS, allow_tools=False)
    OllamaClient("http://o", "m", transport=_mock(ollama)).chat([], TOOLS, allow_tools=False)
    assert seen["anthropic"]["tool_choice"] == {"type": "none"} and seen["anthropic"]["tools"]
    assert "tools" not in seen["ollama"]
