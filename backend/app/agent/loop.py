"""The bounded agent loop (no framework, decision 0004).

1. The model gets the system prompt, the history, the designer's message and the tools.
2. Each model call either answers in text (the run ends) or asks for tool calls; the loop
   runs them through the registry and sends the results back.
3. The run makes at most `max_iterations` model calls, the final answer included: the last
   allowed call offers no tools, so the model must answer with what it has.

An answer that says a confirmation card is shown when none is waiting (a small local model
copies such sentences from its earlier answers) gets one backend note and another try; if it
still claims one, the answer is corrected. The backend knows which cards exist, so it does
not let the text say otherwise (invariant 3 for actions).

The loop yields events for the UI as they happen (`thinking`, `tool_call`, `tool_result`,
`parameter_proposal`, `preview`, `pending_action`, `message`, `error`) and records
everything in an `AgentTrace` (invariant 7). It never executes a side effect: the gated tools
only open confirmation cards (invariant 2).
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from app.agent.tools import ToolContext, ToolRegistry
from app.agent.trace import AgentTrace
from app.llm.base import LLMClient, LLMError, Message

LIMIT_FALLBACK = (
    "I couldn't finish within the steps allowed for one answer. Tell me what to do next, or "
    "check the parameter panel."
)
EMPTY_FALLBACK = "I have no answer for that. Could you rephrase it?"

# An answer that says a confirmation card is shown, in English or Spanish.
_CARD_CLAIM = re.compile(
    r"confirmation card|card is (now )?(shown|displayed|open|waiting)|click\W{0,3}confirm"
    r"|pending (your )?confirmation|awaiting (your )?confirmation"
    r"|tarjeta de confirmaci[oó]n|clic en\W{0,3}confirmar|pendiente de (tu )?confirmaci[oó]n",
    re.IGNORECASE,
)
CARD_CHECK = (
    "<bead_studio_check>\nWritten by the Bead Studio backend: your answer says a confirmation "
    "card is shown, but you called no request_ tool in this answer, so no card exists. If the "
    "designer asked for that step, call the request_ tool now. Otherwise answer again without "
    "saying a card is shown.\n</bead_studio_check>"
)
CARD_CORRECTION = (
    "(Bead Studio: no confirmation card was opened in this answer, so nothing is waiting for "
    "your click. Ask again for the step you want.)"
)


def claims_a_card(text: str) -> bool:
    return bool(_CARD_CLAIM.search(text))


def _card_waiting(ctx: ToolContext) -> bool:
    """A card opened in this run, or one still pending from an earlier answer."""
    if ctx.opened_actions:
        return True
    return any(
        a.status == "pending" and not a.expired for a in ctx.store.list_actions(ctx.conversation_id)
    )


@dataclass(frozen=True)
class AgentEvent:
    type: str
    data: dict[str, Any]


@dataclass
class RunOutcome:
    """Filled while the loop runs: the messages to keep in the history and the answer."""

    new_messages: list[Message] = field(default_factory=list)
    answer: str = ""
    status: str = "running"  # answered | limit | error


def run_agent(
    client: LLMClient,
    registry: ToolRegistry,
    ctx: ToolContext,
    messages: list[Message],
    *,
    max_iterations: int,
    trace: AgentTrace,
    outcome: RunOutcome,
) -> Iterator[AgentEvent]:
    """`messages` = system prompt + history + the new user message."""
    conversation = list(messages)
    trace.record_input(conversation)
    specs = registry.specs
    nudged = False

    for iteration in range(1, max_iterations + 1):
        last_call = iteration == max_iterations
        offered = [] if last_call else specs
        started = time.perf_counter()
        try:
            turn = client.chat(conversation, specs, allow_tools=not last_call)
        except LLMError as exc:
            trace.status, trace.error = "error", str(exc)
            outcome.status = "error"
            yield AgentEvent("error", {"message": str(exc)})
            return
        trace.record_model_call(
            iteration, [s.name for s in offered], turn, (time.perf_counter() - started) * 1000
        )

        if not turn.tool_calls or last_call:
            answer = turn.content.strip()
            false_claim = claims_a_card(answer) and not _card_waiting(ctx)
            if false_claim and not last_call and not nudged:
                # The backend knows no card was opened: one more try, with a note. Neither
                # the claim nor the note is kept in the conversation history.
                nudged = True
                trace.record_check(iteration, "card_claim_without_card")
                conversation += [Message("assistant", answer), Message("user", CARD_CHECK)]
                continue
            # "limit": the tools were withheld on this call (tool calls are ignored).
            status = "limit" if last_call and max_iterations > 1 else "answered"
            answer = answer or (LIMIT_FALLBACK if status == "limit" else EMPTY_FALLBACK)
            if false_claim:
                trace.record_check(iteration, "card_claim_corrected")
                answer += "\n\n" + CARD_CORRECTION
            outcome.new_messages.append(Message("assistant", answer))
            outcome.answer, outcome.status = answer, status
            trace.status = status
            yield AgentEvent("message", {"role": "assistant", "content": answer})
            return

        assistant = Message(
            "assistant",
            turn.content,
            tool_calls=turn.tool_calls,
            provider_content=turn.provider_content,
        )
        conversation.append(assistant)
        outcome.new_messages.append(assistant)
        if turn.content.strip():
            yield AgentEvent("thinking", {"content": turn.content.strip()})

        for call in turn.tool_calls:
            yield AgentEvent(
                "tool_call", {"id": call.id, "name": call.name, "arguments": call.arguments}
            )
            started = time.perf_counter()
            result = registry.execute(call, ctx)
            text = result.for_model()
            trace.record_tool_call(
                iteration,
                call.name,
                call.arguments,
                text,
                result.ok,
                (time.perf_counter() - started) * 1000,
            )
            yield AgentEvent(
                "tool_result",
                {"id": call.id, "name": call.name, "ok": result.ok, "result": result.content},
            )
            if result.event is not None:
                event = dict(result.event)
                yield AgentEvent(event.pop("type"), event)
            tool_message = Message(
                "tool", text, tool_call_id=call.id, name=call.name, is_error=not result.ok
            )
            conversation.append(tool_message)
            outcome.new_messages.append(tool_message)
