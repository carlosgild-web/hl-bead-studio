"""Answers built from a parameter tool's result, in English or Spanish.

Shared by the ideal scripts of `agent-eval --fake` (`app/eval/scenarios.py`) and by demo
mode (`app/llm/demo.py`, decision 0022): every number in these answers comes from the tool
result (invariant 3). With `labels=True` (demo mode) the family and the parameters are
named as the panel names them; without, as the tool names them (the eval scripts).
"""

from __future__ import annotations

import json
from typing import Any, Literal

from app.llm.base import Message
from app.standards.families import FAMILY_CODES, get_family

Language = Literal["en", "es"]
PARAM_TOOLS = ("validate_parameters", "propose_parameters", "preview_geometry")


def mm(value: Any, language: str) -> str:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return str(value)
    text = f"{float(value):.1f}"
    return (text.replace(".", ",") if language == "es" else text) + " mm"


def value_text(name: str, value: Any, language: str) -> str:
    return mm(value, language) if name.endswith("_mm") else str(value)


def _label(family: str, name: str, language: str, labels: bool) -> str:
    if not labels or family not in FAMILY_CODES:
        return name
    prop = get_family(family).parameters.get(name, {})
    return prop.get("x-label", {}).get(language, name)


def _family(family: str, language: str, labels: bool) -> str:
    if not labels or family not in FAMILY_CODES:
        return family
    return get_family(family).label.get(language, family)


def newest_param_result(messages: list[Message], *, broken: bool = False) -> dict[str, Any]:
    """The newest parameter tool result (with violations, if `broken`)."""
    return next(
        json.loads(m.content)
        for m in reversed(messages)
        if m.role == "tool" and m.name in PARAM_TOOLS and (not broken or "violations" in m.content)
    )


def summary_text(result: dict[str, Any], language: str, *, labels: bool = False) -> str:
    """The parameters of a valid result."""
    family = result["family"]
    values = ", ".join(
        f"{_label(family, k, language, labels)} {value_text(k, v, language)}"
        for k, v in result["params"].items()
    )
    name = _family(family, language, labels)
    if language == "es":
        return f"Propuse un {name} en el panel: {values}. Cumple el manual."
    return f"I put a {name} in the panel: {values}. It passes the manual."


def explain_text(
    result: dict[str, Any], language: str, extra: str = "", *, labels: bool = False
) -> str:
    """The rule ids and the nearest valid values of a result with violations."""
    family = result["family"]
    either, near_label, breaks = (
        (" o ", "lo más cercano", "No cumple la regla")
        if language == "es"
        else (" or ", "nearest valid", "It breaks")
    )
    parts = []
    for v in result["violations"]:
        near = either.join(
            f"{_label(family, s['parameter'], language, labels)} "
            f"{value_text(s['parameter'], s['value'], language)}"
            for s in v.get("nearest_valid", [])
        )
        parts.append(f"{breaks} {v['rule']}" + (f"; {near_label}: {near}" if near else ""))
    return ". ".join(parts) + "." + (f" {extra}" if extra else "")
