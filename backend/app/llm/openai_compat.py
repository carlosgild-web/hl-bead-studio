"""A cloud provider that speaks the OpenAI Chat Completions API, over httpx (decision 0016).

Two presets (decisions 0016 and 0017): Dahl (`LLM_PROVIDER=dahl`), an open-models API, and
Groq (`LLM_PROVIDER=groq`), whose free tier has small per-minute token limits. Other
OpenAI-compatible providers can reuse the class with their own base URL. Request choices:

- only standard parameters: Dahl rejects unknown ones;
- `tools` as OpenAI functions. On the loop's last call (`allow_tools=False`) Dahl gets the
  tools with `tool_choice: "none"`; Groq gets no tools, because its gpt-oss models may call a
  tool anyway and Groq then answers 400 "Tool choice is none, but model called a tool". That
  400 is also retried once without tools, whatever the preset;
- every tool result is its own `tool` message with the `tool_call_id` it answers;
- reasoning models (MiniMax M2) may put `<think>...</think>` in the content: it is removed
  from the answer, but the raw assistant message is replayed unchanged to the same provider
  within a run (`provider_content`), as those models expect;
- 408, 429 and 5xx are retried, honouring `retry-after` up to `max_retry_wait` (a preset with
  a per-minute token limit waits longer and retries more);
- `max_tokens` is per preset: Groq counts it against the per-minute limit before answering.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from typing import Any

import httpx

from app.llm.base import (
    DAILY_LIMIT,
    ChatTurn,
    LLMClient,
    LLMError,
    Message,
    ToolCall,
    ToolSpec,
    retry_wait,
)

DAHL_URL = "https://inference.dahl.global/v1"
GROQ_URL = "https://api.groq.com/openai/v1"
MAX_TOKENS = 8000
DEFAULT_TIMEOUT_S = 120.0
RETRIES = 2
MAX_RETRY_WAIT_S = 10.0
RETRY_STATUS = frozenset({408, 429, 500, 502, 503, 504})

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_TOOL_CHOICE_NONE = "Tool choice is none, but model called a tool"
# Groq: "Rate limit reached ... on tokens per day (TPD): Limit 200000, Used ..."
_PER_DAY_RE = re.compile(r"per day|\((?:TPD|RPD)\)", re.IGNORECASE)


class OpenAICompatClient(LLMClient):
    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        provider: str = "dahl",
        base_url: str = DAHL_URL,
        key_env: str = "DAHL_API_KEY",
        model_env: str = "DAHL_MODEL",
        timeout: float = DEFAULT_TIMEOUT_S,
        max_tokens: int = MAX_TOKENS,
        tools_when_off: bool = True,
        retries: int = RETRIES,
        max_retry_wait: float = MAX_RETRY_WAIT_S,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key:
            raise LLMError(f"LLM_PROVIDER={provider} needs {key_env}.")
        self.provider = provider
        self.model = model
        self._name = provider.capitalize()
        self._key_env, self._model_env = key_env, model_env
        self._sleep = sleep
        self._max_tokens, self._retries, self._max_retry_wait = max_tokens, retries, max_retry_wait
        self._tools_when_off = tools_when_off
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            transport=transport,
            headers={"authorization": f"Bearer {api_key}", "content-type": "application/json"},
        )

    def chat(
        self, messages: list[Message], tools: list[ToolSpec], *, allow_tools: bool = True
    ) -> ChatTurn:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": to_openai(messages, self.provider),
            "max_tokens": self._max_tokens,
        }
        if tools and (allow_tools or self._tools_when_off):
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]
            if not allow_tools:
                body["tool_choice"] = "none"
        try:
            return from_openai(self._post(body), self.provider)
        except LLMError as exc:
            if allow_tools or "tools" not in body or _TOOL_CHOICE_NONE not in str(exc):
                raise
        body.pop("tools")
        body.pop("tool_choice", None)
        return from_openai(self._post(body), self.provider)

    def close(self) -> None:
        self._http.close()

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(self._retries + 1):
            try:
                response = self._http.post("/chat/completions", json=body)
            except httpx.TimeoutException as exc:
                if attempt < self._retries:
                    continue
                raise LLMError(f"The {self._name} API took too long to answer ({exc}).") from exc
            except httpx.HTTPError as exc:
                raise LLMError(
                    f"The {self._name} API is not reachable ({exc.__class__.__name__}). Check "
                    "the network connection."
                ) from exc
            if response.is_success:
                try:
                    return response.json()
                except ValueError as exc:
                    raise LLMError(
                        f"The {self._name} API sent an answer that is not JSON."
                    ) from exc
            if response.status_code == 429 and _PER_DAY_RE.search(response.text):
                raise LLMError(self._daily_limit_text(response))
            if response.status_code in RETRY_STATUS and attempt < self._retries:
                self._sleep(retry_wait(response, attempt, self._max_retry_wait))
                continue
            raise LLMError(self._error_text(response))
        raise AssertionError("unreachable")  # pragma: no cover

    def _daily_limit_text(self, response: httpx.Response) -> str:
        wait = re.search(r"try again in ([\w.]+)", response.text)
        when = f" Try again in {wait.group(1)}." if wait else " Try again tomorrow."
        return f"{DAILY_LIMIT} on the {self._name} API for {self.model}.{when}"

    def _error_text(self, response: httpx.Response) -> str:
        try:
            error = response.json().get("error") or {}
            reason = error.get("message", "") if isinstance(error, dict) else str(error)
        except ValueError:
            reason = response.text.strip()
        status, name = response.status_code, self._name
        if status == 401:
            return f"The {name} API rejected the key. Check {self._key_env}."
        if status == 402:
            return f"The {name} key has no tokens left. Allocate tokens to it, then try again."
        if status == 413:
            return (
                f"The request is larger than the {name} per-minute token limit ({reason}). Use "
                "a model with a higher limit or a paid tier."
            )
        if status == 404:
            return f"The {name} API has no model '{self.model}'. Check {self._model_env}."
        if status == 429:
            return (
                f"The {name} API is busy or rate limited ({reason or status}); try again shortly."
            )
        return f"{name} API error {status} for {self.model}: {reason}"


# --- translation -------------------------------------------------------------------------


def to_openai(messages: list[Message], provider: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "tool":
            content = m.content if not m.is_error else f"ERROR: {m.content}"
            out.append({"role": "tool", "tool_call_id": m.tool_call_id, "content": content})
        elif m.role == "assistant":
            stored = m.provider_content
            if isinstance(stored, dict) and stored.get("provider") == provider:
                out.append(dict(stored["message"]))
                continue
            message: dict[str, Any] = {"role": "assistant", "content": m.content or None}
            if m.tool_calls:
                message["tool_calls"] = [_call_out(c) for c in m.tool_calls]
            elif not m.content:
                message["content"] = "(no answer)"
            out.append(message)
        else:
            out.append({"role": m.role, "content": m.content or "(empty)"})
    return out


def _call_out(call: ToolCall) -> dict[str, Any]:
    return {
        "id": call.id,
        "type": "function",
        "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
    }


def from_openai(data: dict[str, Any], provider: str) -> ChatTurn:
    choices = data.get("choices") or []
    if not choices:
        raise LLMError("The model sent no answer (empty `choices`).")
    choice = choices[0]
    message = choice.get("message") or {}
    raw_content = message.get("content") or ""
    tool_calls = tuple(
        ToolCall(c.get("id") or f"call_{i}", c["function"]["name"], _arguments(c["function"]))
        for i, c in enumerate(message.get("tool_calls") or (), 1)
        if (c.get("function") or {}).get("name")
    )
    if choice.get("finish_reason") == "length" and tool_calls:
        raise LLMError("The model's answer was cut off in the middle of a tool call.")
    replay: dict[str, Any] = {"role": "assistant", "content": raw_content or None}
    if tool_calls:
        replay["tool_calls"] = [_call_out(c) for c in tool_calls]
    elif not raw_content:
        replay["content"] = "(no answer)"
    usage = data.get("usage") or {}
    return ChatTurn(
        content=_THINK_RE.sub("", raw_content).strip(),
        tool_calls=tool_calls,
        prompt_tokens=int(usage.get("prompt_tokens") or 0),
        completion_tokens=int(usage.get("completion_tokens") or 0),
        provider_content={"provider": provider, "message": replay},
    )


def _arguments(function: dict[str, Any]) -> dict[str, Any]:
    """OpenAI sends the arguments as a JSON string; some servers send a dict."""
    raw = function.get("arguments")
    if raw is None or raw == "":
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return {"__invalid__": str(raw)}
    return parsed if isinstance(parsed, dict) else {"__invalid__": str(raw)}
