"""Demo mode: answers from the Q&A bank through the real tools, without a model
(decision 0022).

`DemoClient` keeps no state between calls; it reads the conversation like a model would.

- **Language**: Spanish when the system prompt carries the Spanish `LANGUAGE_LINE`.
- **Designer text**: only the `<designer_text>` block of the newest user message. The
  `<panel>`, `<bead_studio_state>` and `<bead_studio_event>` blocks are data and never
  change the answer (invariant 8).
- **First call of a turn**: the matcher (`demo_match`) picks an entry.
  - A design calls `propose_parameters` with the family defaults and the entry's values.
  - A knowledge entry, or any entry with `search`, calls `search_design_manual`.
  - A how-to or guardrail entry without `search` answers at once.
  - No match gives the bank's fallback.
- **After the tool result**: a design is answered from the result (`demo_text`: a summary,
  or the rule ids and the nearest valid values); any other entry gives its answer.

It never calls a `request_*` tool, so it never opens a card (the Workflow stepper does,
decision 0014). The loop's last call (`allow_tools=False`) always gets text.
"""

from __future__ import annotations

import json
import re

from app.agent.prompts import LANGUAGE_LINE
from app.core.content import QaEntry, qa_bank
from app.llm.base import ChatTurn, LLMClient, Message, ToolSpec
from app.llm.demo_match import match
from app.llm.demo_text import explain_text, summary_text
from app.llm.fake import call, say
from app.standards.families import get_family

_DESIGNER_TEXT = re.compile(r"<designer_text>\n?(.*?)\n?</designer_text>", re.DOTALL)
NO_RESULT = {
    "en": "The check did not answer, so I changed nothing. Try again, or use the panel.",
    "es": "La comprobación no respondió, así que no cambié nada. Inténtalo otra vez o usa "
    "el panel.",
}


def language_of(messages: list[Message]) -> str:
    system = next((m.content for m in messages if m.role == "system"), "")
    return "es" if LANGUAGE_LINE["es"] in system else "en"


def designer_text(messages: list[Message]) -> str:
    """The designer's own words in the newest user message that has them, unquoted."""
    for message in reversed(messages):
        if message.role != "user":
            continue
        found = _DESIGNER_TEXT.search(message.content)
        if found:
            return found.group(1).replace("<\\/", "</")
    return ""


def _turn_messages(messages: list[Message]) -> list[Message]:
    """The messages after the newest user message with designer text (this turn's work)."""
    for index in range(len(messages) - 1, -1, -1):
        m = messages[index]
        if m.role == "user" and _DESIGNER_TEXT.search(m.content):
            return messages[index + 1 :]
    return []


class DemoClient(LLMClient):
    provider = "fake"
    model = "demo"

    def chat(
        self, messages: list[Message], tools: list[ToolSpec], *, allow_tools: bool = True
    ) -> ChatTurn:
        language = language_of(messages)
        found = match(designer_text(messages), language)
        if found is None:
            fallback = qa_bank().fallback
            return say(fallback.es if language == "es" else fallback.en)
        entry = found.entry
        results = [m for m in _turn_messages(messages) if m.role == "tool"]
        if not results:
            first = self._first_call(entry, language) if allow_tools else None
            if first is not None:
                return first
        return say(self._answer(entry, language, results))

    @staticmethod
    def _first_call(entry: QaEntry, language: str) -> ChatTurn | None:
        if entry.kind == "design" and entry.proposal is not None:
            family = entry.proposal.family
            params = get_family(family).defaults() | entry.proposal.params
            return call("propose_parameters", family=family, params=params)
        if entry.search:
            return call("search_design_manual", query=entry.search, language=language)
        return None

    @staticmethod
    def _answer(entry: QaEntry, language: str, results: list[Message]) -> str:
        if entry.kind != "design":
            return entry.text(language).answer
        params = [m for m in results if m.name == "propose_parameters"]
        if not params:
            return NO_RESULT["es" if language == "es" else "en"]
        try:
            result = json.loads(params[-1].content)
        except ValueError:
            return NO_RESULT["es" if language == "es" else "en"]
        if "params" not in result or "family" not in result:
            return NO_RESULT["es" if language == "es" else "en"]
        if result.get("valid", not result.get("violations")):
            return summary_text(result, language, labels=True)
        return explain_text(result, language, labels=True)
