"""The cloud provider: Anthropic's Messages API over httpx, without the SDK (decision 0012).

Request choices for the current models (`ANTHROPIC_MODEL`, default Claude Sonnet 5.5):

- no `temperature`: the current models reject sampling parameters;
- thinking is left at the model's default (adaptive) and `output_config.effort` is
  `medium`, enough for a short tool loop;
- an assistant turn is replayed exactly as the API returned it (`provider_content`, thinking
  blocks included), because thinking blocks are only valid unchanged;
- all tool results of one turn go back in one user message, errors with `is_error`;
- server-side fallback (`fallbacks: "default"`) re-runs a declined request on another model
  inside the same call; a decline that still stands becomes an `LLMError`;
- the stable prefix (tools, system prompt) is cached with top-level `cache_control`;
- 429, 5xx and 529 are retried twice, honouring `retry-after` up to `MAX_RETRY_WAIT_S`.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx

from app.llm.base import ChatTurn, LLMClient, LLMError, Message, ToolCall, ToolSpec

API_URL = "https://api.anthropic.com"
API_VERSION = "2026-10-21"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_TOKENS = 8000
EFFORT = "medium"
DEFAULT_TIMEOUT_S = 120.0
RETRIES = 2
MAX_RETRY_WAIT_S = 10.0
RETRY_STATUS = frozenset({408, 429, 500, 502, 503, 504, 529})
PROVIDER_TAG = "anthropic"


class AnthropicClient(LLMClient):
    provider = "anthropic"

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str = API_URL,
        timeout: float = DEFAULT_TIMEOUT_S,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key:
            raise LLMError("LLM_PROVIDER=anthropic needs ANTHROPIC_API_KEY.")
        self.model = model
        self._sleep = sleep
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            transport=transport,
            headers={
                "x-api-key": api_key,
                "anthropic-version": API_VERSION,
                "anthropic-beta": FALLBACK_BETA,
                "content-type": "application/json",
            },
        )

    def chat(
        self, messages: list[Message], tools: list[ToolSpec], *, allow_tools: bool = True
    ) -> ChatTurn:
        system, converted = to_anthropic(messages)
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            "messages": converted,
            "output_config": {"effort": EFFORT},
            "fallbacks": "default",
            "cache_control": {"type": "ephemeral"},
        }
        if system:
            body["system"] = system
        if tools:
            body["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.parameters}
                for t in tools
            ]
            if not allow_tools:
                body["tool_choice"] = {"type": "none"}
        data = self._post(body)
        return from_anthropic(data)

    def close(self) -> None:
        self._http.close()

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(RETRIES + 1):
            try:
                response = self._http.post("/v1/messages", json=body)
            except httpx.TimeoutException as exc:
                if attempt < RETRIES:
                    continue
                raise LLMError(f"The Anthropic API took too long to answer ({exc}).") from exc
            except httpx.HTTPError as exc:
                raise LLMError(
                    f"The Anthropic API is not reachable ({exc.__class__.__name__}). Check the "
                    "network connection."
                ) from exc
            if response.is_success:
                return response.json()
            if response.status_code in RETRY_STATUS and attempt < RETRIES:
                self._sleep(_retry_wait(response, attempt))
                continue
            raise LLMError(self._error_text(response))
        raise AssertionError("unreachable")  # pragma: no cover

    def _error_text(self, response: httpx.Response) -> str:
        try:
            error = response.json().get("error") or {}
            reason = f"{error.get('type', 'error')}: {error.get('message', '')}".strip()
        except ValueError:
            reason = response.text.strip()
        status = response.status_code
        if status == 401:
            return "The Anthropic API rejected the key. Check ANTHROPIC_API_KEY."
        if status == 404:
            return f"The Anthropic API has no model '{self.model}'. Check ANTHROPIC_MODEL."
        if status in (429, 529):
            return f"The Anthropic API is busy or rate limited ({status}); try again shortly."
        return f"Anthropic API error {status} for {self.model}: {reason}"


def _retry_wait(response: httpx.Response, attempt: int) -> float:
    try:
        wait = float(response.headers.get("retry-after", ""))
    except ValueError:
        wait = 2.0**attempt
    return max(0.0, min(wait, MAX_RETRY_WAIT_S))


# --- translation -------------------------------------------------------------------------


def to_anthropic(messages: list[Message]) -> tuple[str, list[dict[str, Any]]]:
    """System text and the `messages` array. Consecutive user content (tool results, then
    any text) is merged into one user message, as the API expects."""
    system_parts: list[str] = []
    out: list[dict[str, Any]] = []

    def add_user_blocks(blocks: list[dict[str, Any]]) -> None:
        if out and out[-1]["role"] == "user":
            out[-1]["content"].extend(blocks)
        else:
            out.append({"role": "user", "content": blocks})

    for m in messages:
        if m.role == "system":
            system_parts.append(m.content)
        elif m.role == "user":
            add_user_blocks([{"type": "text", "text": m.content or "(empty)"}])
        elif m.role == "tool":
            block: dict[str, Any] = {
                "type": "tool_result",
                "tool_use_id": m.tool_call_id,
                "content": m.content,
            }
            if m.is_error:
                block["is_error"] = True
            add_user_blocks([block])
        else:
            out.append({"role": "assistant", "content": _assistant_blocks(m)})
    return "\n\n".join(p for p in system_parts if p), out


def _assistant_blocks(m: Message) -> list[dict[str, Any]]:
    stored = m.provider_content
    if isinstance(stored, dict) and stored.get("provider") == PROVIDER_TAG:
        return list(stored["content"])
    blocks: list[dict[str, Any]] = []
    if m.content:
        blocks.append({"type": "text", "text": m.content})
    blocks.extend(
        {"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments} for c in m.tool_calls
    )
    return blocks or [{"type": "text", "text": "(no answer)"}]


def from_anthropic(data: dict[str, Any]) -> ChatTurn:
    stop = data.get("stop_reason")
    if stop == "refusal":
        details = data.get("stop_details") or {}
        category = details.get("category") or "unspecified"
        raise LLMError(
            f"The model declined this request (category: {category}). Rephrase the request "
            "or use the parameter panel."
        )
    blocks = list(data.get("content") or [])
    text = "\n".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
    tool_calls = tuple(
        ToolCall(b["id"], b["name"], b.get("input") if isinstance(b.get("input"), dict) else {})
        for b in blocks
        if b.get("type") == "tool_use"
    )
    if stop == "max_tokens" and tool_calls:
        raise LLMError("The model's answer was cut off in the middle of a tool call.")
    usage = data.get("usage") or {}
    prompt = sum(
        int(usage.get(key) or 0)
        for key in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
    )
    return ChatTurn(
        content=text,
        tool_calls=tool_calls,
        prompt_tokens=prompt,
        completion_tokens=int(usage.get("output_tokens") or 0),
        provider_content={"provider": PROVIDER_TAG, "content": blocks},
    )
