"""Measure the approved fonts against CH-03 (`python -m app.cli measure-fonts`).

For every letter, the minimum height is the smallest height (in 0.5 mm steps) from which the
letter passes the smallest-feature check at every larger height up to 30 mm. The font's
minimum in CH-07 is the largest of its letters' minimums, leaving out rare outliers that
are listed as exceptions. The numbers in `standards/rules.py` and the manual come from here.
"""

import string
from dataclasses import dataclass

from app.geometry.profile import check_min_feature, to_polygon
from app.geometry.text import outline_with_cap_height, outline_with_height
from app.standards.rules import CHARM_HEIGHT_MM, ENGRAVING_FONT

_HEIGHTS = [h / 2 for h in range(8, 61)]  # 4.0 … 30.0 mm
_CAP_HEIGHTS = [h / 10 for h in range(15, 81)]  # 1.5 … 8.0 mm


@dataclass(frozen=True)
class LetterMeasure:
    letter: str
    pieces: int
    min_height_mm: float | None  # None: fails up to 30 mm


def _monotonic_min(passes, heights: list[float]) -> float | None:
    minimum = None
    for height in reversed(heights):
        if not passes(height):
            break
        minimum = height
    return minimum


def measure_letter(letter: str, font: str) -> LetterMeasure:
    pieces = check_min_feature(to_polygon(outline_with_height(letter, font, 20.0).faces)).pieces
    if pieces != 1:
        return LetterMeasure(letter, pieces, None)

    def passes(height: float) -> bool:
        return check_min_feature(to_polygon(outline_with_height(letter, font, height).faces)).ok

    return LetterMeasure(letter, 1, _monotonic_min(passes, _HEIGHTS))


def measure_font(font: str) -> list[LetterMeasure]:
    return [measure_letter(letter, font) for letter in string.ascii_uppercase]


def font_minimum(measures: list[LetterMeasure]) -> float:
    """The CH-07 minimum: the largest letter minimum, never below the CH-04 height floor."""
    heights = [m.min_height_mm for m in measures if m.min_height_mm is not None]
    return max([CHARM_HEIGHT_MM[0], *heights])


def measure_engraving_character(char: str) -> float | None:
    """Smallest capital height (0.1 mm steps) from which an engraved character passes."""

    def passes(cap: float) -> bool:
        outline = outline_with_cap_height(char, ENGRAVING_FONT, cap)
        return check_min_feature(to_polygon(outline.faces)).ok

    return _monotonic_min(passes, _CAP_HEIGHTS)
