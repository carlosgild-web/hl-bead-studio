"""Manufacturability validation: the code that decides (invariant 1).

`validate_parameters(family, params)` checks a design against the Product Design Manual in
three stages and returns every violation with its rule id and the nearest valid value(s):

1. GEN-01: lengths are rounded to 0.1 mm (reported as notes, not violations);
2. structure and single-value ranges, from the family's JSON Schema;
3. rules that relate values (walls, proportions, facets, engraving fit, smallest feature),
   computed here. The smallest-feature check (CH-03) builds the charm's outline, so it only
   runs when everything else passes.

Every number in a message is computed from the parameters; the assistant quotes them.
"""

import difflib
import math
import re
from dataclasses import asdict, dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from jsonschema import Draft202012Validator
from shapely.geometry.base import BaseGeometry

from app.geometry import build_model
from app.geometry.charms import (
    engraving_letter_height,
    engraving_profile,
    engraving_width_per_cap,
)
from app.geometry.profile import check_min_feature, to_polygon
from app.standards import rules as R
from app.standards.families import Family, get_family

_EPS = 1e-9


@dataclass(frozen=True)
class Suggestion:
    parameter: str
    value: Any


@dataclass(frozen=True)
class Violation:
    rule: str  # manual rule id, or "SCHEMA" for unknown, missing or mistyped parameters
    parameters: tuple[str, ...]
    message: str
    suggestions: tuple[Suggestion, ...] = ()


@dataclass
class ValidationResult:
    family: str
    params: dict[str, Any]
    violations: list[Violation] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    rule_edition: str = R.RULE_EDITION

    @property
    def ok(self) -> bool:
        return not self.violations

    @property
    def rules(self) -> list[str]:
        return sorted({v.rule for v in self.violations})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {"ok": self.ok}


# ---------------------------------------------------------------- number helpers


def round_step(value: float) -> float:
    """GEN-01: round half up to 0.1 mm (10.25 -> 10.3)."""
    return float(Decimal(repr(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def ceil_step(value: float) -> float:
    return math.ceil(round(value * 10, 6)) / 10


def floor_step(value: float) -> float:
    return math.floor(round(value * 10, 6)) / 10


def _fmt(value: float) -> str:
    return f"{value:.1f}"


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _bounds(family: Family, name: str) -> tuple[float, float]:
    prop = family.parameters[name]
    return prop.get("minimum", -math.inf), prop.get("maximum", math.inf)


def _within(family: Family, name: str, value: float) -> bool:
    low, high = _bounds(family, name)
    return low - _EPS <= value <= high + _EPS


# ---------------------------------------------------------------- stage 2: schema


def _rule_of(family: Family, name: str) -> str:
    return family.parameters[name]["x-rule"][0]


def _text_suggestion(name: str, value: str) -> Any:
    if name == "letter":
        candidate = value.strip().upper()
        return candidate if re.fullmatch(r"[A-Z]", candidate) else None
    candidate = re.sub(r"[^A-Z0-9 ]", "", value.upper())
    candidate = re.sub(r" +", " ", candidate).strip()[: R.ENGRAVING_MAX_CHARS].strip()
    return candidate or None


def _closest_choice(value: str, allowed: list[str]) -> str | None:
    """A close spelling ('ambar' -> 'amber') or a shared word ('rose gold' -> 'gold_plate')."""
    close = difflib.get_close_matches(value.lower(), allowed, n=1, cutoff=0.6)
    if close:
        return close[0]
    words = set(re.split(r"[\s_-]+", value.lower()))
    shared = [a for a in allowed if words & set(a.split("_"))]
    return shared[0] if len(shared) == 1 else None


def _schema_violations(family: Family, params: dict[str, Any]) -> list[Violation]:
    found: list[Violation] = []
    for error in Draft202012Validator(family.schema).iter_errors(params):
        kind = error.validator
        if kind == "additionalProperties":
            for name in sorted(set(params) - set(family.parameters)):
                found.append(
                    Violation(
                        "SCHEMA",
                        (name[:40],),
                        f"Unknown parameter {name[:40]!r} for family {family.code}.",
                    )
                )
            continue
        if kind == "required":
            for name in error.validator_value:
                if name not in error.instance:
                    default = family.parameters[name]["default"]
                    found.append(
                        Violation(
                            "SCHEMA",
                            (name,),
                            f"Missing parameter {name!r}.",
                            (Suggestion(name, default),),
                        )
                    )
            continue
        name = str(error.path[0]) if error.path else ""
        if name not in family.parameters:
            found.append(Violation("SCHEMA", (), error.message[:200]))
            continue
        prop, value = family.parameters[name], error.instance
        unit = " mm" if prop.get("x-unit") == "mm" else ""
        if kind == "type":
            found.append(
                Violation(
                    "SCHEMA",
                    (name,),
                    f"{name} must be of type {prop['type']}.",
                    (Suggestion(name, prop["default"]),),
                )
            )
        elif kind in ("minimum", "maximum"):
            limit = error.validator_value
            word = "at least" if kind == "minimum" else "at most"
            found.append(
                Violation(
                    _rule_of(family, name),
                    (name,),
                    f"{name} is {value}{unit}; it must be {word} {limit}{unit}.",
                    (Suggestion(name, limit),),
                )
            )
        elif kind == "enum":
            allowed = prop["enum"]
            if _is_number(value):
                nearest = min(allowed, key=lambda a: (abs(a - value), -a))
                suggestion: tuple[Suggestion, ...] = (Suggestion(name, nearest),)
                choices = ", ".join(f"{a}" for a in allowed)
            else:
                close = _closest_choice(str(value), allowed)
                suggestion = (Suggestion(name, close),) if close else ()
                choices = ", ".join(allowed)
            found.append(
                Violation(
                    _rule_of(family, name),
                    (name,),
                    f"{str(value)[:40]!r} is not allowed for {name}; "
                    f"choose one of {choices}{unit}.",
                    suggestion,
                )
            )
        elif kind == "pattern":
            fixed = _text_suggestion(name, value) if isinstance(value, str) else None
            found.append(
                Violation(
                    _rule_of(family, name),
                    (name,),
                    f"{name} does not follow the allowed format ({prop['description']})",
                    (Suggestion(name, fixed),) if fixed else (),
                )
            )
        else:
            found.append(Violation(_rule_of(family, name), (name,), error.message[:200]))
    return found


# ---------------------------------------------------------------- stage 3: relational rules


def _smaller_mandrels(hole: float, ok) -> tuple[Suggestion, ...]:
    """The largest mandrel below `hole` that satisfies `ok`, if any (GB-01 sizes)."""
    for size in sorted(R.MANDREL_SIZES_MM, reverse=True):
        if size < hole and ok(size):
            return (Suggestion("hole_mm", size),)
    return ()


def glass_wall_mm(family: str, p: dict[str, Any]) -> float:
    """GB-02 thinnest glass wall around the hole, by the manual's formula per family."""
    h = p["hole_mm"]
    if family == "FAC":
        return p["diameter_mm"] / 2 * math.cos(math.pi / p["facet_count"]) - h / 2
    if family == "LEN":
        return (p["thickness_mm"] - h) / 2
    return (p["diameter_mm"] - h) / 2


def _check_wall(family: Family, p: dict[str, Any]) -> list[Violation]:
    if p["hole_mm"] not in R.MANDREL_SIZES_MM:
        return []
    wall = glass_wall_mm(family.code, p)
    if wall >= R.MIN_GLASS_WALL_MM - _EPS:
        return []
    h, need = p["hole_mm"], R.MIN_GLASS_WALL_MM
    suggestions = list(
        _smaller_mandrels(
            h, lambda s: glass_wall_mm(family.code, p | {"hole_mm": s}) >= need - _EPS
        )
    )
    if family.code == "FAC":
        size_name = "diameter_mm"
        size = ceil_step((need + h / 2) * 2 / math.cos(math.pi / p["facet_count"]))
    elif family.code == "LEN":
        size_name, size = "thickness_mm", ceil_step(h + 2 * need)
    else:
        size_name, size = "diameter_mm", ceil_step(h + 2 * need)
    if _within(family, size_name, size):
        suggestions.append(Suggestion(size_name, size))
    return [
        Violation(
            "GB-02",
            ("hole_mm", size_name),
            f"The glass wall around the {_fmt(h)} mm hole is {wall:.2f} mm; "
            f"it must be at least {_fmt(need)} mm.",
            tuple(suggestions),
        )
    ]


def _check_ratio(
    family: Family,
    p: dict[str, Any],
    rule: str,
    part: str,
    whole: str,
    bounds: tuple[float, float],
    label: str,
) -> list[Violation]:
    value, base = p[part], p[whole]
    low, high = bounds
    ratio = value / base
    if low - _EPS <= ratio <= high + _EPS:
        return []
    suggestions = []
    if ratio < low:
        target_part, target_whole = ceil_step(low * base), floor_step(value / low)
    else:
        target_part, target_whole = floor_step(high * base), ceil_step(value / high)
    if _within(family, part, target_part):
        suggestions.append(Suggestion(part, target_part))
    if _within(family, whole, target_whole):
        suggestions.append(Suggestion(whole, target_whole))
    return [
        Violation(
            rule,
            (part, whole),
            f"The {label} is {ratio * 100:.0f}% of the {whole.removesuffix('_mm')}; it must be "
            f"{low * 100:.0f}–{high * 100:.0f}% ({_fmt(low * base)}–{_fmt(high * base)} mm).",
            tuple(suggestions),
        )
    ]


def _check_facets(family: Family, p: dict[str, Any]) -> list[Violation]:
    found = []
    d, n = p["diameter_mm"], p["facet_count"]
    low, high = R.FACET_COUNT
    if n % 2:
        options = [c for c in (n - 1, n + 1) if low <= c <= high]
        found.append(
            Violation(
                "GB-05",
                ("facet_count",),
                f"{n} facets per row: the facet mold has even divisions only.",
                tuple(Suggestion("facet_count", c) for c in options),
            )
        )
    width = math.pi * d / n
    if width < R.MIN_FACET_WIDTH_MM - _EPS:
        most = math.floor(math.pi * d / R.MIN_FACET_WIDTH_MM + _EPS)
        most -= most % 2
        suggestions = []
        if most >= low:
            suggestions.append(Suggestion("facet_count", most))
        diameter = ceil_step(R.MIN_FACET_WIDTH_MM * n / math.pi)
        if _within(family, "diameter_mm", diameter):
            suggestions.append(Suggestion("diameter_mm", diameter))
        found.append(
            Violation(
                "GB-05",
                ("facet_count", "diameter_mm"),
                f"Each facet is {width:.2f} mm wide at the equator; it must be at least "
                f"{_fmt(R.MIN_FACET_WIDTH_MM)} mm.",
                tuple(suggestions),
            )
        )
    return found


def _check_crescent(family: Family, p: dict[str, Any]) -> list[Violation]:
    found = []
    height = p["height_mm"]
    found += _check_ratio(
        family, p, "CH-08", "crescent_width_mm", "height_mm", R.CRESCENT_WIDTH_RATIO, "band width"
    )
    if p["has_star"]:
        star, most = p["star_diameter_mm"], R.CRESCENT_MAX_STAR_RATIO * height
        if star > most + _EPS:
            suggestions = []
            if _within(family, "star_diameter_mm", floor_step(most)):
                suggestions.append(Suggestion("star_diameter_mm", floor_step(most)))
            taller = ceil_step(star / R.CRESCENT_MAX_STAR_RATIO)
            if _within(family, "height_mm", taller) and not _check_ratio(
                family,
                p | {"height_mm": taller},
                "CH-08",
                "crescent_width_mm",
                "height_mm",
                R.CRESCENT_WIDTH_RATIO,
                "",
            ):
                suggestions.append(Suggestion("height_mm", taller))
            suggestions.append(Suggestion("has_star", False))
            found.append(
                Violation(
                    "CH-08",
                    ("star_diameter_mm", "height_mm"),
                    f"The {_fmt(star)} mm star does not fit inside the curve of a "
                    f"{_fmt(height)} mm crescent; it can be at most {_fmt(floor_step(most))} mm.",
                    tuple(suggestions),
                )
            )
    return found


def _check_initial(family: Family, p: dict[str, Any]) -> list[Violation]:
    font, letter, height = p["font"], p["letter"], p["height_mm"]
    if letter in R.FONT_UNAVAILABLE_LETTERS.get(font, ""):
        others = [
            f for f in R.FONT_MIN_HEIGHT_MM if letter not in R.FONT_UNAVAILABLE_LETTERS.get(f, "")
        ]
        return [
            Violation(
                "CH-07",
                ("letter", "font"),
                f"The letter {letter} is drawn in separate pieces in {font}, so it cannot be cast "
                f"as one charm.",
                tuple(Suggestion("font", f) for f in others),
            )
        ]
    need = max(R.FONT_MIN_HEIGHT_MM[font], R.LETTER_MIN_HEIGHT_MM.get((font, letter), 0.0))
    if height >= need - _EPS:
        return []
    suggestions = [Suggestion("height_mm", need)] if _within(family, "height_mm", need) else []
    for other, minimum in R.FONT_MIN_HEIGHT_MM.items():
        other_need = max(minimum, R.LETTER_MIN_HEIGHT_MM.get((other, letter), 0.0))
        available = letter not in R.FONT_UNAVAILABLE_LETTERS.get(other, "")
        if other != font and available and height >= other_need - _EPS:
            suggestions.append(Suggestion("font", other))
    return [
        Violation(
            "CH-07",
            ("height_mm", "font"),
            f"A {letter} in {font} must be at least {_fmt(need)} mm high so that its thinnest "
            f"stroke and narrowest gap stay at {_fmt(R.MIN_FEATURE_MM)} mm (CH-03).",
            tuple(suggestions),
        )
    ]


def _check_disc(family: Family, p: dict[str, Any]) -> list[Violation]:
    found = []
    t, depth = p["thickness_mm"], p["engraving_depth_mm"]
    if p["engraving"] != "none" and t - depth < R.MIN_FEATURE_MM - _EPS:
        suggestions = []
        shallower = floor_step(t - R.MIN_FEATURE_MM)
        if _within(family, "engraving_depth_mm", shallower):
            suggestions.append(Suggestion("engraving_depth_mm", shallower))
        thicker = ceil_step(depth + R.MIN_FEATURE_MM)
        if _within(family, "thickness_mm", thicker):
            suggestions.append(Suggestion("thickness_mm", thicker))
        found.append(
            Violation(
                "CH-03",
                ("engraving_depth_mm", "thickness_mm"),
                f"Only {t - depth:.1f} mm of metal is left under the {_fmt(depth)} mm engraving; "
                f"at least {_fmt(R.MIN_FEATURE_MM)} mm is needed.",
                tuple(suggestions),
            )
        )
    if p["engraving"] == "text":
        text, d = p["engraving_text"], p["diameter_mm"]
        cap = engraving_letter_height(text, d)
        if cap < R.ENGRAVING_MIN_LETTER_MM - _EPS:
            ratio = engraving_width_per_cap(text)
            need = ceil_step(R.ENGRAVING_MIN_LETTER_MM * ratio / R.ENGRAVING_TEXT_FIT)
            suggestions = []
            if _within(family, "diameter_mm", need):
                suggestions.append(Suggestion("diameter_mm", need))
            found.append(
                Violation(
                    "CH-06",
                    ("engraving_text", "diameter_mm"),
                    f"The text fits the {_fmt(d)} mm disc only with {_fmt(cap)} mm letters; "
                    f"engraved letters must be at least {_fmt(R.ENGRAVING_MIN_LETTER_MM)} mm high. "
                    "Use a shorter text or a larger disc.",
                    tuple(suggestions),
                )
            )
    return found


# ---------------------------------------------------------------- CH-03 smallest feature


def _charm_outline(family: Family, p: dict[str, Any]) -> BaseGeometry | None:
    """What CH-03 analyses: a disc's engraving, or the whole outline of other charms."""
    if family.code == "DSC":
        return engraving_profile(p)
    shape = build_model(family.code, p).shape
    bottom = [f for f in shape.Faces() if f.geomType() == "PLANE" and f.normalAt().z < -0.5]
    return to_polygon(bottom)


def _feature_ok(family: Family, p: dict[str, Any]) -> bool:
    outline = _charm_outline(family, p)
    return outline is None or check_min_feature(outline).ok


def _feature_violation(family: Family, p: dict[str, Any]) -> list[Violation]:
    """Build the charm's outline and check strokes, tips, necks and gaps (CH-03)."""
    outline = _charm_outline(family, p)
    if outline is None:
        return []
    report = check_min_feature(outline)
    if report.ok:
        return []
    problems = []
    if report.thin_feature:
        problems.append("a stroke, tip or neck is narrower")
    if report.narrow_gap:
        problems.append("a gap between features is narrower")
    what = "engraving" if family.code == "DSC" else "outline"
    suggestions = _feature_suggestions(family, p)
    return [
        Violation(
            "CH-03",
            tuple(s.parameter for s in suggestions) or ("height_mm",),
            f"In the charm's {what}, {' and '.join(problems)} than "
            f"{_fmt(R.MIN_FEATURE_MM)} mm (the mold limit).",
            suggestions,
        )
    ]


def _feature_suggestions(family: Family, p: dict[str, Any]) -> tuple[Suggestion, ...]:
    """Nearest valid values found by stepping one parameter (at most a few dozen builds)."""
    if family.code == "CRS" and p["has_star"]:
        star = p["star_diameter_mm"]
        while star - 0.5 >= _bounds(family, "star_diameter_mm")[0] - _EPS:
            star = round(star - 0.5, 1)
            if _feature_ok(family, p | {"star_diameter_mm": star}):
                return (Suggestion("star_diameter_mm", star), Suggestion("has_star", False))
        return (Suggestion("has_star", False),)
    size_name = "diameter_mm" if family.code == "DSC" else "height_mm"
    size, high = p[size_name], _bounds(family, size_name)[1]
    scale_width = family.code == "CRS"
    while size + 0.5 <= high + _EPS:
        size = round(size + 0.5, 1)
        q = p | {size_name: size}
        if scale_width:
            q["crescent_width_mm"] = round(p["crescent_width_mm"] * size / p[size_name], 1)
        if _feature_ok(family, q):
            return (Suggestion(size_name, size),)
    return ()


# ---------------------------------------------------------------- entry point


# The parameters each relational check reads; a check is skipped when one of them already
# broke a single-value rule (its value may be meaningless, for example zero facets).
_INPUTS: dict[str, tuple[str, ...]] = {
    "wall": ("diameter_mm", "thickness_mm", "facet_count", "hole_mm"),
    "facets": ("diameter_mm", "facet_count"),
    "lentil": ("diameter_mm", "thickness_mm"),
    "rondelle": ("diameter_mm", "height_mm"),
    "crescent": ("height_mm", "crescent_width_mm", "star_diameter_mm"),
    "initial": ("letter", "font", "height_mm"),
    "disc": ("diameter_mm", "engraving", "engraving_text", "thickness_mm", "engraving_depth_mm"),
}


def _relational(family: Family, p: dict[str, Any], invalid: set[str]) -> list[Violation]:
    def usable(check: str) -> bool:
        return not (set(_INPUTS[check]) & invalid)

    code, found = family.code, []
    if code in ("RND", "FAC", "LEN", "RON"):
        if usable("wall"):
            found += _check_wall(family, p)
        if code == "FAC" and usable("facets"):
            found += _check_facets(family, p)
        if code == "LEN" and usable("lentil"):
            found += _check_ratio(
                family, p, "GB-04", "thickness_mm", "diameter_mm", R.LENTIL_RATIO, "thickness"
            )
        if code == "RON" and usable("rondelle"):
            found += _check_ratio(
                family, p, "GB-06", "height_mm", "diameter_mm", R.RONDELLE_RATIO, "height"
            )
    elif code == "CRS" and usable("crescent"):
        found += _check_crescent(family, p)
    elif code == "INI" and usable("initial"):
        found += _check_initial(family, p)
    elif code == "DSC" and usable("disc"):
        found += _check_disc(family, p)
    return found


def validate_parameters(family_code: str, params: dict[str, Any]) -> ValidationResult:
    """Validate a design. Raises `UnknownFamilyError` for an unknown family code."""
    family = get_family(family_code)
    if not isinstance(params, dict):
        result = ValidationResult(family.code, {})
        result.violations.append(Violation("SCHEMA", (), "Parameters must be an object."))
        return result

    normalized, notes = dict(params), []
    for name, value in params.items():
        prop = family.parameters.get(name)
        if prop and prop.get("x-step") and _is_number(value):
            rounded = round_step(value)
            if rounded != value:
                notes.append(f"{name}: {value} mm rounded to {_fmt(rounded)} mm (GEN-01)")
            normalized[name] = rounded
    result = ValidationResult(family.code, normalized, notes=notes)

    result.violations += _schema_violations(family, normalized)
    if any(v.rule == "SCHEMA" for v in result.violations):
        return result  # relational rules need every parameter with the right type
    invalid = {name for v in result.violations for name in v.parameters}
    result.violations += _relational(family, normalized, invalid)
    if family.is_charm and not result.violations:
        result.violations += _feature_violation(family, normalized)
    return result
