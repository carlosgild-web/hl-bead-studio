"""Render presets: approved colors and finishes, and the job file Blender reads."""

import ast
from pathlib import Path

import pytest

from app.core.config import REPO_ROOT
from app.core.content import colors, finishes
from app.render.presets import (
    RESOLUTION_PX,
    RenderPresetError,
    finish_options,
    job_spec,
    material_spec,
    resolve_finish,
    srgb_to_linear,
)

FAC = {"diameter_mm": 10.0, "color": "honey"}
CRS = {"height_mm": 16.0, "finish": "rhodium"}


def test_srgb_to_linear() -> None:
    assert srgb_to_linear("#000000") == [0.0, 0.0, 0.0]
    assert srgb_to_linear("#ffffff") == [1.0, 1.0, 1.0]
    assert srgb_to_linear("#808080")[0] == pytest.approx(0.2159, abs=1e-4)
    with pytest.raises(ValueError):
        srgb_to_linear("808080")


def test_beads_offer_the_glass_colors_and_charms_the_finishes() -> None:
    assert finish_options("glass_bead") == list(colors())
    assert finish_options("charm") == ["gold_plate", "rhodium", "antique_bronze"]


def test_the_default_is_the_designs_own_color_or_finish() -> None:
    assert resolve_finish("glass_bead", FAC, None) == "honey"
    assert resolve_finish("charm", CRS, None) == "rhodium"
    assert resolve_finish("glass_bead", FAC, "cobalt") == "cobalt"


@pytest.mark.parametrize(
    ("kind", "params", "finish", "rule"),
    [
        ("glass_bead", FAC, "gold_plate", "GB-07"),  # a plating is not a glass color
        ("charm", CRS, "amber", "CH-05"),  # a glass color is not a plating
        ("charm", CRS, "../../etc", "CH-05"),
    ],
)
def test_rejects_a_color_or_finish_of_the_wrong_kind(
    kind: str, params: dict, finish: str, rule: str
) -> None:
    with pytest.raises(RenderPresetError, match=rule):
        resolve_finish(kind, params, finish)


@pytest.mark.parametrize("color", list(colors()))
def test_every_glass_color_has_glass_numbers(color: str) -> None:
    spec = material_spec("glass_bead", color)

    assert spec["kind"] == "glass"
    assert spec["ior"] == 1.47  # borosilicate, manual 07
    assert spec["transmission"] == colors()[color]["transmission"]
    assert spec["metallic"] == 0.0
    assert all(0.0 <= c <= 1.0 for c in spec["base_color"])


@pytest.mark.parametrize("finish", list(finishes()))
def test_every_finish_is_a_metal(finish: str) -> None:
    spec = material_spec("charm", finish)

    assert spec["kind"] == "metal"
    assert spec["metallic"] == 1.0
    assert spec["roughness"] == finishes()[finish]["roughness"]
    assert spec["transmission"] == 0.0


def test_job_spec_has_every_key_the_blender_script_reads() -> None:
    spec = job_spec("charm", "gold_plate", model_path="m.glb", output_path="o.png", samples=32)

    assert spec["resolution"] == RESOLUTION_PX == 1024
    assert spec["samples"] == 32
    assert spec["rotation_deg"] == [90.0, 0.0, 0.0]  # charms stand up facing the camera
    assert set(spec) == _keys_read_by_render_script()


def _keys_read_by_render_script() -> set[str]:
    """Top-level job keys used as `job["..."]` in blender/render.py (it imports bpy, so it
    is parsed, not imported)."""
    tree = ast.parse(Path(REPO_ROOT / "blender" / "render.py").read_text(encoding="utf-8"))
    return {
        node.slice.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id == "job"
        and isinstance(node.slice, ast.Constant)
    }
