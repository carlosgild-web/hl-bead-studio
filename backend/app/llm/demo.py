"""Demo mode: answers from the Q&A bank through the real tools, without a model
(decision 0022).

`DemoClient` keeps no state between calls; it reads the conversation like a model would.

- **Language**: the message's own (`demo_extract.message_language`), else the language it
  matched in, else Spanish when the system prompt carries the Spanish `LANGUAGE_LINE`.
- **Designer text**: only the `<designer_text>` block of the newest user message. The
  `<panel>`, `<bead_studio_state>` and `<bead_studio_event>` blocks are data and never
  change the answer (invariant 8).
- **First call of a turn**: the matcher (`demo_match`) picks an entry.
  - A design calls `propose_parameters` with the values read from the message
    (`demo_extract`, decision 0023), over the entry's values and the family defaults. A
    statement that names a family and a size is a design even when it matched a knowledge
    entry or nothing.
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
from typing import Any

from app.agent.prompts import LANGUAGE_LINE
from app.core.content import QaEntry, qa_bank
from app.llm.base import ChatTurn, LLMClient, Message, ToolSpec
from app.llm.demo_extract import extract, is_question, message_language
from app.llm.demo_match import match
from app.llm.demo_text import defaults_note, explain_text, summary_text
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
        text = designer_text(messages)
        found = match(text, language_of(messages))
        # The designer's own language wins over the UI's (a Spanish message in the English UI
        # gets a Spanish answer); without a clear hint, the language the message matched in.
        language = message_language(text) or (found.language if found else language_of(messages))
        design = design_values(text, found.entry if found else None)
        if found is None and design is None:
            fallback = qa_bank().fallback
            return say(fallback.es if language == "es" else fallback.en)
        results = [m for m in _turn_messages(messages) if m.role == "tool"]
        if design is not None:
            if not results and allow_tools:
                family, params, _ = design
                return call("propose_parameters", family=family, params=params)
            return say(self._design_answer(language, results, design[2]))
        assert found is not None
        entry = found.entry
        if not results:
            first = self._first_call(entry, language) if allow_tools else None
            if first is not None:
                return first
        return say(entry.text(language).answer)

    @staticmethod
    def _first_call(entry: QaEntry, language: str) -> ChatTurn | None:
        if entry.search:
            return call("search_design_manual", query=entry.search, language=language)
        return None

    @staticmethod
    def _design_answer(language: str, results: list[Message], unread: list[str]) -> str:
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
            text = summary_text(result, language, labels=True)
        else:
            text = explain_text(result, language, labels=True)
        note = defaults_note(result["family"], unread, language)
        return f"{text} {note}" if note else text


def design_values(text: str, entry: QaEntry | None) -> tuple[str, dict[str, Any], list[str]] | None:
    """(family, params, unread) when the message asks for a design, else None.

    A design entry of the bank, or a statement (not a question) that names a family and a
    size: "A 12 mm ruby lentil bead" is a design, "How thin can a lentil bead be?" is not.
    Guardrail and how-to entries are never designs. The values come from the message; the
    entry's values fill only what the message leaves out, and only for the same family.
    """
    kind = entry.kind if entry else None
    proposal = entry.proposal if entry is not None and kind == "design" else None
    if kind in ("guardrail", "howto"):
        return None
    found = extract(text, proposal.family if proposal else None)
    if found.family is None:
        return None
    if proposal is None and (is_question(text) or not _has_size(found.params)):
        return None
    params = get_family(found.family).defaults()
    if proposal is not None and proposal.family == found.family:
        params |= proposal.params
    params |= found.params
    return found.family, params, found.unread


def _has_size(params: dict[str, Any]) -> bool:
    return any(name.endswith("_mm") for name in params)
