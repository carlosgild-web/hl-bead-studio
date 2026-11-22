"""The `qa` suite of `agent-eval` (decision 0022): one scenario per Q&A bank entry and
language, `qa-<entry id>-<lang>`, tagged `("qa", kind)`.

Each scenario is the designer's question as one turn. The expectations come from the
entry's `expect`: rule ids cited, numbers mentioned, the family and parameters of a design,
the tools used, and always no card and no side effect. Under `--fake` the turn has no
script (`fake=None`), so the client is demo mode's `DemoClient`, the "ideal model" for these
questions. On a real provider the same scenarios score how well the model explains the
manual. With `variants`, every phrasing variant is a scenario of its own (`-v1`, `-v2`).
"""

from __future__ import annotations

from app.core.content import QaEntry, qa_bank
from app.eval.scenarios import Expect, Language, Scenario, Turn


def _expect(entry: QaEntry) -> Expect:
    e = entry.expect
    return Expect(
        family=e.family,
        params=dict(e.params),
        valid=e.valid,
        rules=tuple(e.rules),
        mentions=tuple(e.mentions),
        tools=(tuple(e.tools_any),) if e.tools_any else (),
        forbidden=tuple(e.forbidden),
    )


def _scenario(entry: QaEntry, language: Language, text: str, suffix: str = "") -> Scenario:
    return Scenario(
        id=f"qa-{entry.id}-{language}{suffix}",
        title=f"Q&A ({entry.kind}): {entry.id}",
        language=language,
        steps=(Turn(text, fake=None),),
        expect=_expect(entry),
        tags=("qa", entry.kind),
    )


def qa_scenarios(*, variants: bool = False) -> list[Scenario]:
    out: list[Scenario] = []
    for entry in qa_bank().entries:
        for language in ("en", "es"):
            text = entry.text(language)
            out.append(_scenario(entry, language, text.question))
            if variants:
                out += [
                    _scenario(entry, language, variant, f"-v{n}")
                    for n, variant in enumerate(text.variants, 1)
                ]
    return out
