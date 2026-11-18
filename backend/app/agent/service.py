"""One chat turn: load the conversation, run the agent, store the messages and the trace.

Used by `POST /api/chat` (as server-sent events) and by `python -m app.cli chat`.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from app.agent.loop import AgentEvent, RunOutcome, run_agent
from app.agent.prompts import system_prompt, user_message
from app.agent.tools import PreviewCache, ToolContext, ToolRegistry
from app.agent.trace import AgentTrace
from app.core.config import Settings
from app.db.store import Store
from app.llm.base import LLMClient, Message
from app.sap import SapClient
from app.standards.manual_search import ManualIndex


@dataclass
class AgentDeps:
    settings: Settings
    store: Store
    client: LLMClient
    sap: SapClient
    manual: ManualIndex
    previews: PreviewCache
    registry: ToolRegistry = field(default_factory=ToolRegistry)


def model_history(stored: list[dict[str, Any]]) -> list[Message]:
    """What the model sees of earlier turns: the designer's messages, the final answers and
    the Bead Studio events. Tool calls of earlier runs stay in their traces, which keeps the
    context of a small local model short (and no stale thinking blocks are replayed)."""
    history: list[Message] = []
    for data in stored:
        role = data.get("role")
        if role == "user" or (role == "assistant" and not data.get("tool_calls")):
            history.append(Message(role, data.get("content") or ""))
        elif role == "event":
            history.append(Message("user", data.get("content") or ""))
    return history


def chat_turn(
    deps: AgentDeps,
    *,
    text: str,
    conversation_id: str | None = None,
    panel: dict[str, Any] | None = None,
    language: str = "en",
) -> Iterator[AgentEvent]:
    """Yields `conversation` first, then the loop's events, then `done`."""
    stored = deps.store.get_messages(conversation_id) if conversation_id else None
    if stored is None:
        conversation_id = deps.store.create_conversation(language)
        stored = []
    assert conversation_id is not None
    yield AgentEvent("conversation", {"id": conversation_id})

    client = deps.client
    run_id = deps.store.start_run(conversation_id, client.provider, client.model)
    user = {
        "role": "user",
        "content": user_message(text, panel),
        "text": text,
        "panel": panel or {},
    }
    messages = [
        Message("system", system_prompt(language)),
        *model_history(stored),
        Message("user", user["content"]),
    ]
    ctx = ToolContext(
        settings=deps.settings,
        store=deps.store,
        sap=deps.sap,
        manual=deps.manual,
        previews=deps.previews,
        conversation_id=conversation_id,
        run_id=run_id,
        language=language,
    )
    max_iterations = deps.settings.agent_max_iterations
    trace = AgentTrace(client.provider, client.model, max_iterations)
    outcome = RunOutcome()
    try:
        yield from run_agent(
            client,
            deps.registry,
            ctx,
            messages,
            max_iterations=max_iterations,
            trace=trace,
            outcome=outcome,
        )
    finally:
        # Also when the client disconnects mid-stream: keep what happened.
        if outcome.status == "running":
            outcome.status = trace.status = "error"
            trace.error = trace.error or "interrupted"
        kept = [user] + [m.to_dict() for m in outcome.new_messages]
        deps.store.append_messages(conversation_id, kept, run_id=run_id)
        deps.store.finish_run(
            run_id,
            status=outcome.status,
            model_calls=trace.model_calls,
            tokens=trace.tokens,
            trace=trace.to_dict(),
        )
    yield AgentEvent(
        "done", {"conversation_id": conversation_id, "run_id": run_id, "status": outcome.status}
    )


def visible_conversation(store: Store, conversation_id: str) -> dict[str, Any] | None:
    """What the UI shows: the designer's texts, the answers, the events and the cards."""
    messages = store.get_messages(conversation_id)
    if messages is None:
        return None
    visible = []
    for m in messages:
        if m["role"] == "user":
            visible.append({"role": "user", "content": m.get("text", m["content"])})
        elif m["role"] == "assistant" and not m.get("tool_calls"):
            visible.append({"role": "assistant", "content": m["content"]})
        elif m["role"] == "event":
            visible.append({"role": "event", "event": m.get("event", {})})
    actions = [a.to_dict() for a in store.list_actions(conversation_id)]
    return {"id": conversation_id, "messages": visible, "actions": actions}
