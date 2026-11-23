"""Read design values from a designer's message, for demo mode (decision 0023).

Plain regular expressions, no model. Demo mode used to propose the Q&A bank entry's values,
so "a 10 mm faceted bead with a 0.5 mm hole" came back with a 1.5 mm hole and "it passes the
manual". Now the family, sizes, hole, glass color, finish, letter, font and star come from
the message, and the values go to `propose_parameters` unchanged: the real validators judge
them (invariant 1), so an out-of-range value shows its rule and the nearest valid value.

The message is data (invariant 8): nothing here can call a tool or change what the demo
does, only fill parameter values that the validators check.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.core.content import colors, finishes
from app.llm.demo_match import normalize
from app.standards.families import get_family
from app.standards.naming import COLLECTIONS

# Checked in this order: "a disc with a moon" is a disc, "an initial charm" is not a crescent.
_FAMILY_WORDS: tuple[tuple[str, str], ...] = (
    ("DSC", r"disc|disk|disco|medal|medalla|coin|moneda"),
    ("INI", r"initial|inicial|letter|letra"),
    ("CRS", r"crescent|creciente|media luna|half moon|moon charm"),
    ("FAC", r"faceted|facetad[ao]|facet bead"),
    ("RON", r"rondelle|rondel"),
    ("LEN", r"lentil|lenteja"),
    ("RND", r"round|redond[ao]|sphere|esfera"),
)

# Words that say what a number is (before it, or right after its "mm").
_ROLES: tuple[tuple[str, str], ...] = (
    ("hole_mm", r"hole|holes|agujero|agujeros|orificio|perforacion"),
    ("star_diameter_mm", r"star|estrella"),
    ("crescent_width_mm", r"wide|width|band|ancho|ancha|banda"),
    ("thickness_mm", r"thick|thickness|grosor|espesor|grueso|gruesa"),
    ("engraving_depth_mm", r"deep|depth|profundidad|profundo"),
    ("height_mm", r"tall|high|height|alto|alta|altura"),
    ("diameter_mm", r"diameter|diametro|across"),
)
# The role a bare size gets: a bead's or a disc's diameter, a charm's height.
_PRIMARY = ("diameter_mm", "height_mm")

# A number in millimetres, or a bare number (kept only when the word before it names it).
_NUMBER = re.compile(r"(\d+(?:\.\d+)?)(\s*mm\b)?")
_FACETS = re.compile(r"(\d+)\s*(?:facets|facetas)\b")
_PUNCT = re.compile(r"[,;:!?()]|\.\s")
_WORD = re.compile(r"[a-z]+")
# Words skipped between a number and the word that names it: "12 mm de alto", "a hole of 1 mm".
_FILLER_WORDS = "de del of in en a an un una the el la por"
_FILLERS = frozenset(_FILLER_WORDS.split())

_FINISH_EXTRA = {
    "gold_plate": ("gold", "golden", "oro", "dorado", "dorada", "gold plated", "gold-plated"),
    "rhodium": ("silver", "plata", "plateado", "plateada", "rodio"),
    "antique_bronze": ("bronze", "bronce"),
}
_FONT_WORDS = {
    "pacifico": r"pacifico|script|cursiva",
    "cinzel_bold": r"cinzel|serif",
    "montserrat_extrabold": r"montserrat|sans",
}
_LETTER = re.compile(
    r"\b(?:letter|letra|initial|inicial)\s+(?:de\s+|of\s+)?[\"'“]?([^\W\d_])(?![^\W\d_])",
    re.IGNORECASE,
)
_NO_STAR = re.compile(r"\b(?:without|no|sin)\s+(?:a\s+|una\s+)?(?:star|estrella)")
_ES_WORDS = "de la el una un con para en y que cuenta dije agujero alto quiero puedo cual como"
_EN_WORDS = "the a an with for of and bead charm hole tall what how can i want which"
_SPANISH_HINT = frozenset(_ES_WORDS.split())
_ENGLISH_HINT = frozenset(_EN_WORDS.split())
_QUESTION_START = re.compile(
    r"(?:what|how|which|why|can|could|is|are|do|does"
    r"|que|cual|como|cuanto|cuanta|por que|puedo|se puede)"
)


@dataclass
class Extracted:
    family: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    # Parameters the designer named but whose value could not be read (demo used the default).
    unread: list[str] = field(default_factory=list)


def _words(text: str) -> list[str]:
    return _WORD.findall(text)


def family_of(text: str) -> str | None:
    norm = normalize(text)
    for code, pattern in _FAMILY_WORDS:
        if re.search(rf"\b(?:{pattern})\b", norm):
            return code
    return None


def message_language(text: str) -> str | None:
    """Spanish ("es") or English ("en") from common words, or None when the message does not say."""
    words = _words(normalize(text))
    es = sum(w in _SPANISH_HINT for w in words)
    en = sum(w in _ENGLISH_HINT for w in words)
    if es == en:
        return None
    return "es" if es > en else "en"


def is_question(text: str) -> bool:
    return "?" in text or "¿" in text or bool(_QUESTION_START.match(normalize(text).strip()))


def _next_word(words: list[str]) -> str:
    """The first word that is not a filler: the one that names the number next to it."""
    return next((w for w in words if w not in _FILLERS), "")


def _role_near(word: str) -> str | None:
    for name, pattern in _ROLES:
        if re.fullmatch(rf"(?:{pattern})", word):
            return name
    return None


def _sizes(norm: str, properties: dict[str, Any]) -> tuple[dict[str, float], list[str]]:
    found: dict[str, float] = {}
    numbers = [m for m in _NUMBER.finditer(norm) if not _FACETS.match(norm, m.start())]
    for i, m in enumerate(numbers):
        start = numbers[i - 1].end() if i else 0
        end = numbers[i + 1].start() if i + 1 < len(numbers) else len(norm)
        after = norm[m.end() : end]
        cut = _PUNCT.search(after)  # "4 mm, hole 1.5": "hole" names the 1.5, not the 4
        before_role = _role_near(_next_word(_words(norm[start : m.start()])[::-1]))
        if not m.group(2):  # a bare number counts only right after its word: "hole 1.5"
            if before_role in properties:
                found.setdefault(before_role, float(m.group(1)))
            continue
        role = _role_near(_next_word(_words(after[: cut.start()] if cut else after)))
        role = role or before_role
        if role is None or role not in properties:
            role = next((p for p in _PRIMARY if p in properties and p not in found), None)
        if role is not None and role not in found:
            found[role] = float(m.group(1))
    # A role word with no number of its own: the designer named it, demo used the default.
    unread = [
        name
        for name, pattern in _ROLES
        if name in properties
        and name not in found
        and name not in _PRIMARY
        and re.search(rf"\b(?:{pattern})\b", norm)
        and name != "star_diameter_mm"  # "with a star" is has_star, not a size
    ]
    return found, unread


def _names(
    entries: dict[str, dict[str, Any]], extra: dict[str, tuple[str, ...]]
) -> list[tuple[str, str]]:
    """(normalized name, id), longest first, so "rose opal" wins over "opal"."""
    pairs = []
    for key, entry in entries.items():
        names = {key.replace("_", " "), *(normalize(n) for n in entry["name"].values())}
        names.update(extra.get(key, ()))
        pairs += [(normalize(n), key) for n in names]
    return sorted(pairs, key=lambda p: -len(p[0]))


def _choice(norm: str, pairs: list[tuple[str, str]], allowed: list[Any]) -> str | None:
    for name, key in pairs:
        if key in allowed and re.search(rf"(?<![a-z]){re.escape(name)}(?![a-z])", norm):
            return key
    return None


def extract(text: str, fallback_family: str | None = None) -> Extracted:
    """The design values the message gives, for its family (or `fallback_family`)."""
    family = family_of(text) or fallback_family
    out = Extracted(family=family)
    if family is None:
        return out
    properties = get_family(family).parameters
    norm = normalize(text)
    for collection in COLLECTIONS:  # "Amber Hollow" names a collection, not a color
        norm = norm.replace(normalize(collection), " ")
    sizes, out.unread = _sizes(norm, properties)
    out.params.update(sizes)
    facets = _FACETS.search(norm)
    if facets and "facet_count" in properties:
        out.params["facet_count"] = int(facets.group(1))
    if "color" in properties:
        color = _choice(norm, _names(colors(), {}), properties["color"].get("enum", []))
        if color:
            out.params["color"] = color
    if "finish" in properties:
        finish = _choice(
            norm, _names(finishes(), _FINISH_EXTRA), properties["finish"].get("enum", [])
        )
        if finish:
            out.params["finish"] = finish
    if "letter" in properties:
        letter = _LETTER.search(text)
        if letter:
            out.params["letter"] = letter.group(1).upper()
    if "font" in properties:
        for font, pattern in _FONT_WORDS.items():
            if re.search(rf"\b(?:{pattern})\b", norm):
                out.params["font"] = font
                break
    if "has_star" in properties:
        if _NO_STAR.search(norm):
            out.params["has_star"] = False
        elif re.search(r"\b(?:star|estrella)\b", norm):
            out.params["has_star"] = True
    return out
