"""Every family builds a valid solid for any design the validator accepts.

Property-based (Hypothesis): random designs inside the manual's ranges are generated per
family, kept when `validate_parameters` accepts them, built, and checked: one valid closed
solid whose size matches the parameters, and a mass that is volume times density.
The default profile is small and derandomized for CI; `HYPOTHESIS_PROFILE=thorough` runs more.
"""

import os
import string
from typing import Any

import cadquery as cq
import pytest
import trimesh
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from app.core.content import colors, finishes
from app.geometry import build_model
from app.geometry.export import glb_bytes, measure
from app.standards import rules as R
from app.standards.families import get_family
from app.standards.validators import validate_parameters

settings.register_profile(
    "ci",
    max_examples=12,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.filter_too_much, HealthCheck.too_slow],
)
settings.register_profile(
    "thorough",
    max_examples=150,
    deadline=None,
    suppress_health_check=[HealthCheck.filter_too_much, HealthCheck.too_slow],
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))

TOL = 0.02


def tenths(low: float, high: float) -> st.SearchStrategy[float]:
    return st.integers(round(low * 10), round(high * 10)).map(lambda v: v / 10)


holes = st.sampled_from(R.MANDREL_SIZES_MM)
glass = st.sampled_from(sorted(colors()))
plating = st.sampled_from(sorted(finishes()))


@st.composite
def round_beads(draw) -> dict[str, Any]:
    return {"diameter_mm": draw(tenths(4, 20)), "hole_mm": draw(holes), "color": draw(glass)}


@st.composite
def faceted_beads(draw) -> dict[str, Any]:
    return {
        "diameter_mm": draw(tenths(6, 20)),
        "facet_count": draw(st.integers(4, 16)) * 2,
        "facet_rows": draw(st.integers(1, 3)),
        "hole_mm": draw(holes),
        "color": draw(glass),
    }


@st.composite
def lentils(draw) -> dict[str, Any]:
    d = draw(tenths(4, 20))
    ratio = draw(st.floats(*R.LENTIL_RATIO))
    return {
        "diameter_mm": d,
        "thickness_mm": round(d * ratio, 1),
        "hole_mm": draw(holes),
        "color": draw(glass),
    }


@st.composite
def rondelles(draw) -> dict[str, Any]:
    d = draw(tenths(4, 20))
    ratio = draw(st.floats(*R.RONDELLE_RATIO))
    return {
        "diameter_mm": d,
        "height_mm": round(d * ratio, 1),
        "hole_mm": draw(holes),
        "color": draw(glass),
    }


def charm_common(draw) -> dict[str, Any]:
    return {
        "thickness_mm": draw(tenths(*R.CHARM_THICKNESS_MM)),
        "loop_inner_mm": draw(tenths(1.5, 4.0)),
        "loop_wall_mm": draw(tenths(0.8, 2.0)),
        "finish": draw(plating),
    }


@st.composite
def crescents(draw) -> dict[str, Any]:
    h = draw(tenths(*R.CHARM_HEIGHT_MM))
    return charm_common(draw) | {
        "height_mm": h,
        "crescent_width_mm": round(h * draw(st.floats(*R.CRESCENT_WIDTH_RATIO)), 1),
        "has_star": draw(st.booleans()),
        "star_diameter_mm": draw(tenths(3.0, 8.0)),
    }


@st.composite
def initials(draw) -> dict[str, Any]:
    font = draw(st.sampled_from(sorted(R.FONT_MIN_HEIGHT_MM)))
    return charm_common(draw) | {
        "letter": draw(st.sampled_from(string.ascii_uppercase)),
        "font": font,
        "height_mm": draw(tenths(R.FONT_MIN_HEIGHT_MM[font], 30.0)),
    }


@st.composite
def discs(draw) -> dict[str, Any]:
    text = draw(st.text(alphabet=string.ascii_uppercase + string.digits, min_size=1, max_size=5))
    return charm_common(draw) | {
        "diameter_mm": draw(tenths(12, 30)),
        "engraving": draw(st.sampled_from(["none", "text", "icon"])),
        "engraving_text": text,
        "icon": draw(st.sampled_from(["moon", "star", "heart", "leaf", "bee", "wave"])),
        "engraving_depth_mm": draw(tenths(*R.ENGRAVING_DEPTH_MM)),
    }


def build_valid(code: str, params: dict[str, Any]):
    result = validate_parameters(code, params)
    assume(result.ok)
    model = build_model(code, result.params)
    shape = model.shape
    assert shape.isValid()
    assert len(shape.Solids()) == 1
    measured = measure(shape, get_family(code).material)
    assert measured.volume_mm3 > 0
    assert measured.mass_g == pytest.approx(
        shape.Volume() / 1000 * measured.density_g_cm3, abs=1e-3
    )
    return result.params, shape.BoundingBox(), model


@given(round_beads())
def test_round_beads(p: dict) -> None:
    p, box, _ = build_valid("RND", p)
    assert box.xlen == pytest.approx(p["diameter_mm"], abs=TOL)
    assert box.ylen == pytest.approx(p["diameter_mm"], abs=TOL)


@given(faceted_beads())
def test_faceted_beads(p: dict) -> None:
    p, box, _ = build_valid("FAC", p)
    assert box.xlen == pytest.approx(p["diameter_mm"], abs=TOL)  # across the facet corners
    assert box.ylen <= p["diameter_mm"] + TOL


@given(lentils())
def test_lentils(p: dict) -> None:
    p, box, _ = build_valid("LEN", p)
    assert box.xlen == pytest.approx(p["diameter_mm"], abs=TOL)
    assert box.ylen == pytest.approx(p["thickness_mm"], abs=TOL)


@given(rondelles())
def test_rondelles(p: dict) -> None:
    p, box, _ = build_valid("RON", p)
    assert box.xlen == pytest.approx(p["diameter_mm"], abs=TOL)
    assert box.zlen == pytest.approx(p["height_mm"], abs=TOL)


def check_charm_box(p: dict, box, body_height: float) -> None:
    assert box.zlen == pytest.approx(p["thickness_mm"], abs=TOL)
    assert box.ymin == pytest.approx(0, abs=0.05)
    assert box.ymax > body_height  # the loop sits above the body


@given(crescents())
def test_crescents(p: dict) -> None:
    p, box, _ = build_valid("CRS", p)
    check_charm_box(p, box, p["height_mm"])


@given(initials())
def test_initials(p: dict) -> None:
    p, box, _ = build_valid("INI", p)
    check_charm_box(p, box, p["height_mm"])


@given(discs())
def test_discs(p: dict) -> None:
    p, box, _ = build_valid("DSC", p)
    assert box.xlen == pytest.approx(p["diameter_mm"], abs=TOL)
    check_charm_box(p, box, p["diameter_mm"])


# ---------------------------------------------------------------- targeted checks


def test_engraving_removes_metal() -> None:
    base = get_family("DSC").defaults()
    plain = build_model("DSC", base | {"engraving": "none"}).shape.Volume()
    engraved = build_model("DSC", base).shape.Volume()

    assert 0 < plain - engraved < plain * 0.05


def test_hole_goes_through_every_bead() -> None:
    for code in ("RND", "FAC", "LEN", "RON"):
        shape = build_model(code, get_family(code).defaults()).shape
        # a thin rod along Z through the center stays in the hole: no material on it
        probe = cq.Solid.makeCylinder(0.1, 100, cq.Vector(0, 0, -50))
        assert shape.intersect(probe).Volume() == pytest.approx(0, abs=1e-6), code


def test_glb_is_a_metre_scaled_mesh() -> None:
    shape = build_model("RND", get_family("RND").defaults()).shape
    scene = trimesh.load(trimesh.util.wrap_as_stream(glb_bytes(shape)), file_type="glb")
    mesh = scene.to_geometry() if hasattr(scene, "to_geometry") else scene.dump(concatenate=True)

    assert mesh.extents.max() == pytest.approx(0.008, rel=0.01)  # 8 mm bead in metres
