"""The fallback chain for a cloud provider with a quota (decision 0018).

The public demo runs on Groq's free tier, whose daily limit can run out. Then a chat turn
moves to the next provider in `LLM_FALLBACK` that is available: the local Ollama model when
it answers (a designer's own PC), else the fake client (demo mode). The answer starts with a
note that says so, so the designer knows why it reads differently.

The switch is process-wide and happens once (decision 0019): the chat builds a client per
turn, and after the first daily limit `make_client` returns the chosen fallback directly
until the app restarts, so later turns do not ask the used-up provider again.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import replace

import httpx

from app.llm.base import DAILY_LIMIT, ChatTurn, LLMClient, LLMError, Message, ToolSpec

OLLAMA_PROBE_TIMEOUT_S = 1.5

NOTES = {
    "ollama": (
        "{name}'s free daily quota is used up, so this answer comes from the local Ollama "
        "model ({model})."
    ),
    "fake": (
        "{name}'s free daily quota is used up; the assistant is in demo mode until it resets "
        "(the parameter panel, the checks and the cards still work). To keep chatting, run "
        "the studio locally with Ollama: start.cmd ollama."
    ),
}


_switch_lock = threading.Lock()
_switched_to: str | None = None


def switched_to() -> str | None:
    """The fallback every client uses after a daily limit in this process, or None."""
    return _switched_to


def record_switch(name: str) -> None:
    """Remember the first fallback chosen; a later or concurrent switch keeps it."""
    global _switched_to
    with _switch_lock:
        if _switched_to is None:
            _switched_to = name


def reset_switch() -> None:
    """Forget the switch (tests)."""
    global _switched_to
    with _switch_lock:
        _switched_to = None


def ollama_available(
    base_url: str, model: str, *, transport: httpx.BaseTransport | None = None
) -> bool:
    """Ollama answers at `base_url` and has `model` pulled."""
    try:
        with httpx.Client(timeout=OLLAMA_PROBE_TIMEOUT_S, transport=transport) as http:
            response = http.get(f"{base_url.rstrip('/')}/api/tags")
            response.raise_for_status()
            names = [m.get("name", "") for m in response.json().get("models", [])]
    except (httpx.HTTPError, ValueError):
        return False
    return any(model_matches(name, model) for name in names)


def model_matches(pulled: str, model: str) -> bool:
    """`qwen3:4b-instruct-2507` matches the pulled `qwen3:4b-instruct-2507-q4_K_M`; a name
    without a tag matches `name:latest`."""
    return pulled == model or pulled.startswith(model)


class FallbackClient(LLMClient):
    """The primary client until it reports its daily limit, then the first available
    fallback for the rest of the turn. `fallbacks` are (name, factory) pairs; a factory
    returns None when that provider is not available."""

    def __init__(
        self,
        primary: LLMClient,
        fallbacks: list[tuple[str, Callable[[], LLMClient | None]]],
    ) -> None:
        self._primary = primary
        self._fallbacks = fallbacks
        self._active = primary
        self._note: str | None = None
        self.provider = primary.provider
        self.model = primary.model

    def chat(
        self, messages: list[Message], tools: list[ToolSpec], *, allow_tools: bool = True
    ) -> ChatTurn:
        try:
            turn = self._active.chat(messages, tools, allow_tools=allow_tools)
        except LLMError as exc:
            if self._active is not self._primary or not str(exc).startswith(DAILY_LIMIT):
                raise
            self._switch()
            turn = self._active.chat(messages, tools, allow_tools=allow_tools)
        if self._note and (turn.content or not turn.tool_calls):
            turn = replace(turn, content=f"_{self._note}_\n\n{turn.content}".rstrip())
            self._note = None
        return turn

    def _switch(self) -> None:
        for name, factory in self._fallbacks:
            client = factory()
            if client is None:
                continue
            self._active = client
            record_switch(name)
            self._note = NOTES.get(name, "{name} is not available; using {model}.").format(
                name=self._primary.provider.capitalize(), model=client.model
            )
            return
        raise LLMError(f"{DAILY_LIMIT} and no fallback provider is available.")

    def close(self) -> None:
        self._primary.close()
        if self._active is not self._primary:
            self._active.close()
