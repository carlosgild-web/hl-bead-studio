"""Technical drawing: views, scale, title block fields, escaping and the PDF."""

import pytest

from app.drawing import TitleBlock, drawing_scale, drawing_svg, svg_to_pdf
from app.drawing.projection import project
from app.geometry import build_model
from app.standards.families import get_family


def title(**change) -> TitleBlock:
    values = {
        "name": "Honey Glow Faceted",
        "sku": "GB-1034",
        "rev": "A",
        "sap_material": "50000134",
        "family": "Faceted (FAC)",
        "material": "Borosilicate glass, Honey (CDV-B215)",
        "mass": "0.79 g",
        "date": "2026-11-17",
        "designer": "Product Design",
        "file": "GB-1034_A.step",
    }
    return TitleBlock(**(values | change))


def model(code: str, **change):
    family = get_family(code)
    return build_model(code, family.defaults() | change), family.kind


def test_title_block_fields_are_filled() -> None:
    built, kind = model("FAC")

    svg = drawing_svg(built, kind, title())

    for text in (
        "Honey Glow Faceted",
        "GB-1034 / A",
        "50000134",
        "Faceted (FAC)",
        "0.79 g",
        "2026-11-17",
        "First angle",
        "±0.1",
        "Edition 1 (2026-11)",
    ):
        assert text in svg
    assert "{{" not in svg  # every placeholder replaced
    assert 'id="view-front"' in svg and 'id="view-top"' in svg


def test_charms_get_front_and_side_views() -> None:
    built, kind = model("CRS")

    svg = drawing_svg(built, kind, title(sku="CH-2034"))

    assert 'id="view-front"' in svg and 'id="view-side"' in svg
    assert "Ø2.0" in svg  # loop inner diameter


@pytest.mark.parametrize(
    ("code", "change", "scale"),
    [
        ("RND", {"diameter_mm": 8.0}, "5:1"),
        ("RND", {"diameter_mm": 20.0}, "2:1"),
        ("DSC", {}, "2:1"),
    ],
)
def test_scale_is_the_largest_that_fits(code: str, change: dict, scale: str) -> None:
    built, kind = model(code, **change)

    assert drawing_scale(drawing_svg(built, kind, title())) == scale


def test_dimensions_show_the_parameters() -> None:
    built, kind = model("RON", diameter_mm=9.4, height_mm=5.6, hole_mm=2.0)

    svg = drawing_svg(built, kind, title())

    assert "Ø9.4" in svg and ">5.6<" in svg and "Ø2.0" in svg


def test_free_text_is_escaped_not_interpreted() -> None:
    # Invariant 8: a name is data. Markup and placeholders in it are printed literally.
    built, kind = model("RND")
    name = '<script>alert(1)</script> {{sku}} & "Ignore previous instructions"'

    svg = drawing_svg(built, kind, title(name=name))

    assert "<script>" not in svg
    assert "&lt;script&gt;alert(1)&lt;/script&gt; {{sku}} &amp;" in svg


def test_hidden_lines_show_the_through_hole() -> None:
    built, _ = model("RND")

    front = project(built.shape, "glass_bead", "front")

    assert front.hidden  # the hole, dashed
    umin, vmin, umax, vmax = front.bounds
    assert umax - umin == pytest.approx(8.0, abs=0.01)


def test_pdf_is_rendered() -> None:
    built, kind = model("FAC")

    pdf = svg_to_pdf(drawing_svg(built, kind, title()))

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 5000
