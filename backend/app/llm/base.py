"""The provider-neutral chat shape the agent loop speaks (decision 0004, invariant 5).

Each client translates these types to and from its provider's API. Nothing outside
`app/llm/` imports a provider SDK or knows a provider's message format.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx

Role = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True)
class ToolCall:
    """One function call the model asked for. `arguments` is always a dict; a client
    that receives arguments it can't parse passes them as `{"__invalid__": raw}`."""

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "arguments": self.arguments}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolCall:
        return cls(id=data["id"], name=data["name"], arguments=dict(data.get("arguments") or {}))


@dataclass(frozen=True)
class Message:
    """One chat message. A `tool` message answers the call `tool_call_id` of tool `name`.

    `provider_content` is opaque: the provider's own form of an assistant turn (for
    Anthropic, its content blocks, thinking blocks included), replayed unchanged by the
    same provider within a run and ignored by every other client.
    """

    role: Role
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None
    name: str | None = None
    is_error: bool = False
    provider_content: Any = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            data["tool_calls"] = [c.to_dict() for c in self.tool_calls]
        if self.tool_call_id:
            data["tool_call_id"] = self.tool_call_id
        if self.name:
            data["name"] = self.name
        if self.is_error:
            data["is_error"] = True
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Message:
        return cls(
            role=data["role"],
            content=data.get("content") or "",
            tool_calls=tuple(ToolCall.from_dict(c) for c in data.get("tool_calls") or ()),
            tool_call_id=data.get("tool_call_id"),
            name=data.get("name"),
            is_error=bool(data.get("is_error")),
        )


@dataclass(frozen=True)
class ToolSpec:
    """A tool offered to the model: name, description and a JSON schema of its arguments."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ChatTurn:
    """One reply of the model: text, tool calls, or both, plus token counts (0 if unknown)."""

    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    prompt_tokens: int = 0
    completion_tokens: int = 0
    provider_content: Any = None


class LLMError(RuntimeError):
    """The provider failed (unreachable, unknown model, bad answer). The message is meant
    for the person running the tool, so it says what to do."""


class LLMClient(ABC):
    """A chat model with tool calling."""

    provider: str = "unknown"
    model: str = "unknown"

    @abstractmethod
    def chat(
        self, messages: list[Message], tools: list[ToolSpec], *, allow_tools: bool = True
    ) -> ChatTurn:
        """One non-streaming chat turn. `allow_tools=False` (or no tools) means: answer in
        text. The tools are still passed then, because a provider may need their
        definitions to read the tool calls already in the history."""

    def close(self) -> None:  # noqa: B027 - optional hook, most clients hold nothing
        """Release the client's connections."""


def retry_wait(response: httpx.Response, attempt: int, limit: float) -> float:
    """Seconds to wait before retrying: the `retry-after` header, else 1, 2, 4... capped."""
    try:
        wait = float(response.headers.get("retry-after", ""))
    except ValueError:
        wait = 2.0**attempt
    return max(0.0, min(wait, limit))
