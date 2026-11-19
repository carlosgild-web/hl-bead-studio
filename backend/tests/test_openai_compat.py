"""The OpenAI-compatible client (Dahl preset), with mocked transports: no key or network."""

import json

import httpx
import pytest

from app.llm import LLMError, Message, ToolCall, ToolSpec, make_client
from app.llm.openai_compat import DAHL_URL, OpenAICompatClient, from_openai, to_openai
from tests.conftest import make_settings

TOOLS = [ToolSpec("list_families", "List the families", {"type": "object", "properties": {}})]
SECRET = "sk-dahl-secret-123"


def _reply(content=None, tool_calls=None, finish="stop", usage=None):
    message = {"role": "assistant", "content": content}
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    return {
        "choices": [{"index": 0, "message": message, "finish_reason": finish}],
        "usage": usage or {"prompt_tokens": 12, "completion_tokens": 5},
    }


def _call(id_, name, arguments):
    return {"id": id_, "type": "function", "function": {"name": name, "arguments": arguments}}


def _client(handler, **kw):
    return OpenAICompatClient(
        SECRET, "MiniMaxAI/MiniMax-M2.7", transport=httpx.MockTransport(handler), **kw
    )


def test_request_shape_auth_and_only_standard_parameters():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_reply("Hi"))

    turn = _client(handler).chat(
        [Message("system", "rules"), Message("user", "hello")], TOOLS, allow_tools=True
    )
    body = seen["body"]
    assert seen["url"] == f"{DAHL_URL}/chat/completions"
    assert seen["auth"] == f"Bearer {SECRET}"
    assert set(body) == {"model", "messages", "max_tokens", "tools"}
    assert body["messages"][0] == {"role": "system", "content": "rules"}
    assert body["tools"][0]["type"] == "function"
    assert body["tools"][0]["function"]["name"] == "list_families"
    assert (turn.content, turn.prompt_tokens, turn.completion_tokens) == ("Hi", 12, 5)


def test_reads_tool_calls_with_string_or_dict_arguments():
    data = _reply(
        None,
        [_call("c1", "validate_parameters", '{"family": "FAC"}'), _call("c2", "x", {"a": 1})],
        finish="tool_calls",
    )
    turn = from_openai(data, "dahl")
    assert turn.tool_calls == (
        ToolCall("c1", "validate_parameters", {"family": "FAC"}),
        ToolCall("c2", "x", {"a": 1}),
    )


def test_unparsable_arguments_reach_the_loop_as_invalid():
    turn = from_openai(_reply(None, [_call("c1", "x", "{not json")]), "dahl")
    assert turn.tool_calls[0].arguments == {"__invalid__": "{not json"}


def test_think_blocks_are_dropped_from_the_answer_but_replayed():
    turn = from_openai(_reply("<think>plan</think>\nThe bead is valid."), "dahl")
    assert turn.content == "The bead is valid."
    replay = to_openai(
        [Message("assistant", turn.content, provider_content=turn.provider_content)], "dahl"
    )
    assert replay == [{"role": "assistant", "content": "<think>plan</think>\nThe bead is valid."}]


def test_history_of_other_providers_is_rebuilt_with_tool_call_ids():
    messages = [
        Message("user", "go"),
        Message(
            "assistant",
            tool_calls=(ToolCall("ollama_1", "list_families", {}),),
            provider_content={"provider": "anthropic", "content": []},
        ),
        Message("tool", '{"ok": true}', tool_call_id="ollama_1", name="list_families"),
        Message("tool", "boom", tool_call_id="ollama_2", name="x", is_error=True),
    ]
    out = to_openai(messages, "dahl")
    assert out[1]["content"] is None
    assert out[1]["tool_calls"][0]["id"] == "ollama_1"
    assert out[1]["tool_calls"][0]["function"]["arguments"] == "{}"
    assert out[2] == {"role": "tool", "tool_call_id": "ollama_1", "content": '{"ok": true}'}
    assert out[3]["content"] == "ERROR: boom"


def test_last_call_keeps_the_tools_but_turns_them_off():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, json=_reply("ok"))

    _client(handler).chat([], TOOLS, allow_tools=False)
    assert seen["tool_choice"] == "none" and seen["tools"]


def test_retries_busy_then_succeeds():
    replies = [
        httpx.Response(429, headers={"retry-after": "3"}, json={"error": {"message": "busy"}}),
        httpx.Response(503),
        httpx.Response(200, json=_reply("ok")),
    ]
    waits = []
    client = _client(lambda request: replies.pop(0), sleep=waits.append)
    assert client.chat([], []).content == "ok"
    assert waits == [3.0, 2.0]


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, "rejected the key. Check DAHL_API_KEY"),
        (402, "no tokens left"),
        (404, "no model 'MiniMaxAI/MiniMax-M2.7'. Check DAHL_MODEL"),
        (400, "Dahl API error 400 for MiniMaxAI/MiniMax-M2.7: unsupported parameter"),
    ],
)
def test_errors_say_what_to_do_and_never_show_the_key(status, expected):
    def handler(request):
        return httpx.Response(status, json={"error": {"message": "unsupported parameter"}})

    with pytest.raises(LLMError) as info:
        _client(handler).chat([], [])
    assert expected in str(info.value)
    assert SECRET not in str(info.value)


def test_cut_off_tool_call_is_an_error():
    with pytest.raises(LLMError, match="cut off"):
        from_openai(_reply(None, [_call("c1", "x", '{"a"')], finish="length"), "dahl")


def test_empty_choices_is_an_error():
    with pytest.raises(LLMError, match="no answer"):
        from_openai({"choices": []}, "dahl")


def test_factory_dahl(tmp_path):
    settings = make_settings(
        tmp_path, llm_provider="dahl", dahl_api_key=SECRET, dahl_model="deepseek-ai/x"
    )
    client = make_client(settings)
    assert (client.provider, client.model) == ("dahl", "deepseek-ai/x")
    client.close()


def test_factory_dahl_without_key_explains(tmp_path, monkeypatch):
    monkeypatch.delenv("DAHL_API_KEY", raising=False)
    with pytest.raises(LLMError, match="DAHL_API_KEY"):
        make_client(make_settings(tmp_path, llm_provider="dahl", dahl_api_key=None))
