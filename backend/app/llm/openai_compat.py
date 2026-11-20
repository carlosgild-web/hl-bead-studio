"""A cloud provider that speaks the OpenAI Chat Completions API, over httpx (decision 0016).

Two presets (decisions 0016 and 0017): Dahl (`LLM_PROVIDER=dahl`), an open-models API, and
Groq (`LLM_PROVIDER=groq`), whose free tier has small per-minute token limits. Other
OpenAI-compatible providers can reuse the class with their own base URL. Request choices:

- only standard parameters: Dahl rejects unknown ones;
- `tools` as OpenAI functions. On the loop's last call (`allow_tools=False`) Dahl gets the
  tools with `tool_choice: "none"`. Groq's gpt-oss models call a tool anyway, even with no
  tools in the request, and Groq answers 400 "Tool choice is none, but model called a tool".
  So Groq gets no tools and the history as plain text (`to_text_only`), with an instruction
  to answer now; any preset falls back to that form after that 400;
- every tool result is its own `tool` message with the `tool_call_id` it answers;
- reasoning models (MiniMax M2) may put `<think>...</think>` in the content: it is removed
  from the answer, but the raw assistant message is replayed unchanged to the same provider
  within a run (`provider_content`), as those models expect;
- 408, 429 and 5xx are retried, honouring `retry-after` up to `max_retry_wait` (a preset with
  a per-minute token limit waits longer and retries more). A 429 for a daily quota, by its
  text or by a wait over a minute (`ratelimit.classify_429`), is never waited for;
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
from app.llm.ratelimit import RateLimit, classify_429

DAHL_URL = "https://inference.dahl.global/v1"
GROQ_URL = "https://api.groq.com/openai/v1"
MAX_TOKENS = 8000
DEFAULT_TIMEOUT_S = 120.0
RETRIES = 2
MAX_RETRY_WAIT_S = 10.0
RETRY_STATUS = frozenset({408, 429, 500, 502, 503, 504})

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_TOOL_CHOICE_NONE = "Tool choice is none, but model called a tool"


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
        text_only = not allow_tools and not self._tools_when_off
        body: dict[str, Any] = {
            "model": self.model,
            "messages": to_text_only(messages) if text_only else to_openai(messages, self.provider),
            "max_tokens": self._max_tokens,
        }
        if tools and not text_only:
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
            if allow_tools or text_only or _TOOL_CHOICE_NONE not in str(exc):
                raise
        body.pop("tools", None)
        body.pop("tool_choice", None)
        body["messages"] = to_text_only(messages)
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
            limit = classify_429(response) if response.status_code == 429 else None
            if limit is not None and limit.kind == "day":
                raise LLMError(self._daily_limit_text(response, limit))
            if response.status_code in RETRY_STATUS and attempt < self._retries:
                wait = retry_wait(response, attempt, self._max_retry_wait)
                if limit is not None and limit.wait_s is not None:
                    wait = min(limit.wait_s, self._max_retry_wait)
                self._sleep(wait)
                continue
            raise LLMError(self._error_text(response))
        raise AssertionError("unreachable")  # pragma: no cover

    def _daily_limit_text(self, response: httpx.Response, limit: RateLimit) -> str:
        said = re.search(r"try again in ([\w.]+)", response.text)
        if said:
            when = f" Try again in {said.group(1).rstrip('.')}."
        elif limit.reset:
            when = f" Try again {limit.reset}."
        else:
            when = " Try again tomorrow."
        usage = f" ({limit.usage})" if limit.usage else ""
        return f"{DAILY_LIMIT} on the {self._name} API for {self.model}.{when}{usage}"

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


ANSWER_NOW = (
    "Tools are no longer available in this turn. Using only the tool results above, write "
    "your answer to the designer now, in plain text. Do not call any tool."
)


def to_text_only(messages: list[Message]) -> list[dict[str, Any]]:
    """The history without tool-call structure, for a call that must answer in text: tool
    calls and results become plain messages, and an instruction to answer closes it."""
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "tool":
            label = "error" if m.is_error else "result"
            out.append({"role": "user", "content": f"[tool {label}: {m.name}]\n{m.content}"})
        elif m.role == "assistant":
            calls = "; ".join(f"{c.name}({json.dumps(c.arguments)})" for c in m.tool_calls)
            parts = [m.content.strip(), f"[called {calls}]" if calls else ""]
            text = "\n".join(p for p in parts if p)
            out.append({"role": "assistant", "content": text or "-"})
        else:
            out.append({"role": m.role, "content": m.content or "(empty)"})
    out.append({"role": "user", "content": ANSWER_NOW})
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
