"""Product names (GEN-03): the pattern `<Evocative name> <Family>`, unique in the catalog.

The catalog comes from SAP (`SapClient.list_materials`); this module only compares names,
so it is deterministic and needs no network. Names of discontinued products count: they are
never reused.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Iterable
from dataclasses import dataclass

from app.standards.families import Family
from app.standards.validators import Suggestion, Violation

RULE = "GEN-03"
MAX_LENGTH = 40  # SAP material description (MAKTX)
WORDS = (2, 4)
_WORD = re.compile(r"^[A-Z][a-z]+(?:['-][A-Za-z][a-z]*)*$")
SIMILAR_LIMIT = 5
COLLECTIONS = ("Permanente", "Coastal Garden", "Amber Hollow")  # manual 06, Collections


@dataclass(frozen=True)
class CatalogEntry:
    sku: str
    name: str
    status: str


def _key(name: str) -> str:
    return " ".join(name.lower().split())


def find_same_name(name: str, catalog: Iterable[CatalogEntry]) -> CatalogEntry | None:
    key = _key(name)
    return next((e for e in catalog if _key(e.name) == key), None)


def similar_names(name: str, catalog: Iterable[CatalogEntry]) -> list[CatalogEntry]:
    """Products whose name is close, or shares an evocative word (not the family word)."""
    words = set(_key(name).split()[:-1])
    scored = []
    for entry in catalog:
        ratio = difflib.SequenceMatcher(None, _key(name), _key(entry.name)).ratio()
        shared = words & set(_key(entry.name).split())
        if ratio >= 0.6 or shared:
            scored.append((ratio + 0.2 * len(shared), entry))
    scored.sort(key=lambda pair: -pair[0])
    return [entry for _, entry in scored[:SIMILAR_LIMIT]]


def suggest_name(text: str, family: Family) -> str | None:
    """A mechanical fix of what a designer typed: words in Title Case, at most three of them
    before the family word, which is added once at the end ("amber  glow" ->
    "Amber Glow Faceted"). None when there is no word to work with."""
    suffix = family.name_suffix
    words = [
        w[0].upper() + w[1:].lower()
        for w in re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", text)
        if w.lower() != suffix.lower()
    ][: WORDS[1] - 1]
    while words and len(" ".join([*words, suffix])) > MAX_LENGTH:
        words.pop()
    return " ".join([*words, suffix]) if words else None


def validate_product_name(
    name: str, family: Family, catalog: Iterable[CatalogEntry]
) -> list[Violation]:
    """Every GEN-03 violation of a new product's name, with a suggestion when one is
    mechanical (adding the family word)."""
    catalog = list(catalog)
    words = name.split()
    problems: list[str] = []
    problems_es: list[str] = []
    suggestions: list[Suggestion] = []

    if len(name) > MAX_LENGTH:
        problems.append(f"it has {len(name)} characters; SAP keeps at most {MAX_LENGTH}")
        problems_es.append(f"tiene {len(name)} caracteres; SAP guarda como máximo {MAX_LENGTH}")
    if not WORDS[0] <= len(words) <= WORDS[1]:
        problems.append(f"it has {len(words)} words; a name has {WORDS[0]}-{WORDS[1]}")
        problems_es.append(
            f"tiene {len(words)} palabras; un nombre tiene de {WORDS[0]} a {WORDS[1]}"
        )
    bad = [w for w in words if not _WORD.match(w)]
    if bad:
        problems.append(
            "every word is an English word in Title Case (" + ", ".join(repr(w) for w in bad) + ")"
        )
        problems_es.append(
            "cada palabra es una palabra inglesa con la inicial en mayúscula ("
            + ", ".join(repr(w) for w in bad)
            + ")"
        )
    if not words or words[-1] != family.name_suffix:
        problems.append(f"the last word must be the family name '{family.name_suffix}'")
        problems_es.append(
            f"la última palabra debe ser el nombre de la familia '{family.name_suffix}'"
        )
        if words and len(words) < WORDS[1] and family.name_suffix not in words:
            suggestions.append(Suggestion("name", f"{' '.join(words)} {family.name_suffix}"))

    violations = []
    if problems:
        violations.append(
            Violation(
                RULE,
                ("name",),
                f"'{name}' does not follow the naming pattern: " + "; ".join(problems) + ".",
                tuple(suggestions),
                message_es=f"'{name}' no sigue el patrón de nombres: "
                + "; ".join(problems_es)
                + ".",
            )
        )
    same = find_same_name(name, catalog)
    if same:
        violations.append(
            Violation(
                RULE,
                ("name",),
                f"'{same.name}' already exists ({same.sku}, {same.status}); names are unique "
                "and never reused.",
                message_es=f"'{same.name}' ya existe ({same.sku}, {same.status}); los nombres "
                "son únicos y nunca se reutilizan.",
            )
        )
    return violations
