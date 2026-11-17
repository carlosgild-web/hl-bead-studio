"""CH-03 smallest-feature check, and the measured font table behind CH-07 and CH-06."""

import string

import pytest
from shapely.geometry import Point, box
from shapely.ops import unary_union

from app.geometry.font_metrics import measure_letter
from app.geometry.profile import check_min_feature, to_polygon
from app.geometry.text import outline_with_height
from app.standards import rules as R


def test_wide_strokes_pass() -> None:
    assert check_min_feature(box(0, 0, 10, 1.0)).ok


def test_a_stroke_under_the_limit_disappears() -> None:
    report = check_min_feature(box(0, 0, 10, 0.5))

    assert report.thin_feature and not report.ok


def test_a_thin_neck_splits_the_shape() -> None:
    dumbbell = unary_union([box(0, 0, 3, 3), box(3, 1.3, 6, 1.7), box(6, 0, 9, 3)])

    report = check_min_feature(dumbbell)

    assert report.thin_feature


def test_a_narrow_gap_closes() -> None:
    two_blocks = unary_union([box(0, 0, 3, 3), box(3.4, 0, 6.4, 3)])

    assert check_min_feature(two_blocks).narrow_gap
    assert check_min_feature(unary_union([box(0, 0, 3, 3), box(3.7, 0, 6.7, 3)])).ok


def test_a_small_counter_fills_in() -> None:
    ring = Point(0, 0).buffer(2).difference(Point(0, 0).buffer(0.25))

    assert check_min_feature(ring).narrow_gap


def test_exactly_the_limit_passes() -> None:
    assert check_min_feature(box(0, 0, 10, R.MIN_FEATURE_MM)).ok


@pytest.mark.parametrize("font", sorted(R.FONT_MIN_HEIGHT_MM))
def test_every_letter_passes_at_its_ch07_minimum(font: str) -> None:
    unavailable = R.FONT_UNAVAILABLE_LETTERS.get(font, "")
    for letter in string.ascii_uppercase:
        if letter in unavailable:
            continue
        height = max(R.FONT_MIN_HEIGHT_MM[font], R.LETTER_MIN_HEIGHT_MM.get((font, letter), 0))
        outline = to_polygon(outline_with_height(letter, font, height).faces)
        assert check_min_feature(outline).ok, (font, letter, height)


def test_the_font_minimums_are_tight() -> None:
    # One letter below its minimum fails, so the minimums are not just generous guesses.
    assert measure_letter("G", "pacifico").min_height_mm == R.FONT_MIN_HEIGHT_MM["pacifico"]
    assert (
        measure_letter("Y", "pacifico").min_height_mm == R.LETTER_MIN_HEIGHT_MM[("pacifico", "Y")]
    )
    assert measure_letter("E", "cinzel_bold").min_height_mm == R.FONT_MIN_HEIGHT_MM["cinzel_bold"]


def test_cinzel_k_is_two_pieces() -> None:
    assert measure_letter("K", "cinzel_bold").pieces == 2
    assert R.FONT_UNAVAILABLE_LETTERS["cinzel_bold"] == "K"
