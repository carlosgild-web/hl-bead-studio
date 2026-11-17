"""Phase 1 content checks: family schemas, manual rule ids, colors, finishes and materials.

These files are company content, not code, so the tests guard their shape and keep them
consistent with each other (a rule cited by a schema must exist in both manuals, the color
enum must match the color list, and so on).
"""

import json
import re
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from app.core.config import REPO_ROOT

SCHEMAS_DIR = REPO_ROOT / "backend" / "app" / "standards" / "schemas"
MANUAL_DIR = REPO_ROOT / "docs" / "manual"
TEMPLATES_DIR = REPO_ROOT / "cad" / "templates"

FAMILIES = {
    "RND": "glass_bead",
    "FAC": "glass_bead",
    "LEN": "glass_bead",
    "RON": "glass_bead",
    "CRS": "charm",
    "INI": "charm",
    "DSC": "charm",
}
RULE_IDS = (
    {f"GEN-0{i}" for i in range(1, 5)}
    | {f"GB-0{i}" for i in range(1, 8)}
    | {f"CH-0{i}" for i in range(1, 9)}
)
RULE_HEADING = re.compile(r"^#{2,3} ((?:GEN|GB|CH)-\d{2}) ", re.MULTILINE)
RULE_MENTION = re.compile(r"\b(?:GEN|GB|CH)-\d{2}\b")
HEX = re.compile(r"^#[0-9a-f]{6}$")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_schema(code: str) -> dict[str, Any]:
    return load_json(SCHEMAS_DIR / f"{code}.schema.json")


def defaults_of(schema: dict[str, Any]) -> dict[str, Any]:
    return {name: prop["default"] for name, prop in schema["properties"].items()}


def manual_rule_headings(lang: str) -> list[str]:
    text = "\n".join(
        p.read_text(encoding="utf-8") for p in sorted((MANUAL_DIR / lang).glob("*.md"))
    )
    return RULE_HEADING.findall(text)


# ---------------------------------------------------------------- family schemas


def test_there_is_one_schema_per_family() -> None:
    assert {p.name.removesuffix(".schema.json") for p in SCHEMAS_DIR.glob("*.schema.json")} == set(
        FAMILIES
    )


@pytest.mark.parametrize("code", sorted(FAMILIES))
def test_schema_is_valid_json_schema(code: str) -> None:
    Draft202012Validator.check_schema(load_schema(code))


@pytest.mark.parametrize("code", sorted(FAMILIES))
def test_schema_family_metadata(code: str) -> None:
    family = load_schema(code)["x-family"]

    assert family["code"] == code
    assert family["kind"] == FAMILIES[code]
    expected = ("GB", "borosilicate") if FAMILIES[code] == "glass_bead" else ("CH", "zinc_alloy")
    assert (family["sku_prefix"], family["material"]) == expected
    assert family["label"]["en"] == family["name_suffix"]
    assert family["label"]["es"]


@pytest.mark.parametrize("code", sorted(FAMILIES))
def test_defaults_are_a_valid_design(code: str) -> None:
    schema = load_schema(code)

    errors = list(Draft202012Validator(schema).iter_errors(defaults_of(schema)))

    assert errors == []


@pytest.mark.parametrize("code", sorted(FAMILIES))
def test_every_parameter_has_unit_rule_and_labels(code: str) -> None:
    for name, prop in load_schema(code)["properties"].items():
        assert prop.get("x-rule"), f"{code}.{name} cites no rule"
        assert set(prop["x-label"]) == {"en", "es"}, f"{code}.{name} labels"
        assert prop.get("description"), f"{code}.{name} has no description"
        if prop["type"] == "number":
            assert prop["x-unit"] == "mm", f"{code}.{name} has no mm unit"
            assert name.endswith("_mm"), f"{code}.{name}: lengths are named *_mm"


@pytest.mark.parametrize("code", sorted(FAMILIES))
def test_unknown_parameters_are_rejected(code: str) -> None:
    schema = load_schema(code)
    design = defaults_of(schema) | {"ignore_the_rules": True}

    assert not Draft202012Validator(schema).is_valid(design)


@pytest.mark.parametrize(
    ("code", "change"),
    [
        ("RND", {"diameter_mm": 3.9}),  # GB-03
        ("RND", {"hole_mm": 1.2}),  # GB-01: not a mandrel size
        ("FAC", {"diameter_mm": 5.0}),  # GB-03: faceted beads >= 6 mm
        ("FAC", {"facet_count": 34}),  # GB-05
        ("FAC", {"facet_rows": 0}),  # GB-05
        ("RND", {"color": "neon_pink"}),  # GB-07
        ("CRS", {"thickness_mm": 0.8}),  # CH-01
        ("CRS", {"loop_wall_mm": 0.6}),  # CH-02
        ("INI", {"height_mm": 32.0}),  # CH-04
        ("INI", {"finish": "rose_gold"}),  # CH-05
        ("INI", {"letter": "a"}),  # CH-07: capitals only
        ("INI", {"letter": "AB"}),  # CH-07: one letter
        ("INI", {"font": "comic_sans"}),  # CH-07
        ("DSC", {"engraving_text": "HILDA AND LUNA"}),  # CH-06: 14 characters
        ("DSC", {"engraving_text": "luna"}),  # CH-06: capitals only
        ("DSC", {"engraving_depth_mm": 0.5}),  # CH-06
    ],
)
def test_out_of_range_values_fail(code: str, change: dict[str, Any]) -> None:
    schema = load_schema(code)

    assert not Draft202012Validator(schema).is_valid(defaults_of(schema) | change)


def test_disc_engraving_needs_its_text_or_icon() -> None:
    schema = load_schema("DSC")
    validator = Draft202012Validator(schema)
    base = {k: v for k, v in defaults_of(schema).items() if k not in ("engraving_text", "icon")}

    assert not validator.is_valid(base | {"engraving": "text"})
    assert not validator.is_valid(base | {"engraving": "icon"})
    assert validator.is_valid(base | {"engraving": "icon", "icon": "bee"})
    assert validator.is_valid(base | {"engraving": "none"})


def test_color_and_finish_enums_match_the_approved_lists() -> None:
    colors = [c["id"] for c in load_json(TEMPLATES_DIR / "colors.json")["colors"]]
    finishes = [f["id"] for f in load_json(TEMPLATES_DIR / "finishes.json")["finishes"]]

    for code, kind in FAMILIES.items():
        props = load_schema(code)["properties"]
        if kind == "glass_bead":
            assert props["color"]["enum"] == colors
        else:
            assert props["finish"]["enum"] == finishes


# ---------------------------------------------------------------- manual


def test_manual_has_the_same_files_in_both_languages() -> None:
    en = sorted(p.name for p in (MANUAL_DIR / "en").glob("*.md"))
    es = sorted(p.name for p in (MANUAL_DIR / "es").glob("*.md"))

    assert en == es
    assert len(en) == 8


@pytest.mark.parametrize("lang", ["en", "es"])
def test_every_rule_has_exactly_one_heading(lang: str) -> None:
    headings = manual_rule_headings(lang)

    assert sorted(headings) == sorted(RULE_IDS)  # each id once, none missing, none extra


@pytest.mark.parametrize("lang", ["en", "es"])
def test_manual_only_mentions_defined_rules(lang: str) -> None:
    for path in (MANUAL_DIR / lang).glob("*.md"):
        unknown = set(RULE_MENTION.findall(path.read_text(encoding="utf-8"))) - RULE_IDS
        assert not unknown, f"{lang}/{path.name} mentions undefined rules {unknown}"


def test_every_rule_cited_by_a_schema_exists() -> None:
    cited = {
        rule
        for code in FAMILIES
        for prop in load_schema(code)["properties"].values()
        for rule in prop["x-rule"]
    }

    assert cited <= RULE_IDS
    # Every design rule (GB, CH) is reachable from at least one parameter.
    assert {r for r in RULE_IDS if not r.startswith("GEN")} <= cited


# ---------------------------------------------------------------- colors, finishes, materials


def test_colors_are_well_formed() -> None:
    colors = load_json(TEMPLATES_DIR / "colors.json")["colors"]

    assert len({c["id"] for c in colors}) == len(colors)
    assert len({c["supplier_code"] for c in colors}) == len(colors)
    for color in colors:
        assert HEX.match(color["hex"]), color["id"]
        assert 0.0 <= color["transmission"] <= 1.0, color["id"]
        assert color["blender_preset"] in {"glass_clear", "glass_translucent", "glass_opaque"}
        assert color["name"]["en"] and color["name"]["es"]


def test_finishes_are_the_three_plating_lines() -> None:
    finishes = load_json(TEMPLATES_DIR / "finishes.json")["finishes"]

    assert [f["id"] for f in finishes] == ["gold_plate", "rhodium", "antique_bronze"]
    for finish in finishes:
        assert HEX.match(finish["hex"]), finish["id"]
        assert 0.0 <= finish["roughness"] <= 1.0
        assert finish["blender_preset"].startswith("metal_")
        assert finish["name"]["en"] and finish["name"]["es"]


def test_material_densities_match_the_plan() -> None:
    materials = {m["id"]: m for m in load_json(TEMPLATES_DIR / "materials.json")["materials"]}

    assert materials["borosilicate"]["density_g_cm3"] == 2.23
    assert materials["borosilicate"]["ior"] == 1.47
    assert materials["zinc_alloy"]["density_g_cm3"] == 6.6


def test_title_block_logo_is_an_svg() -> None:
    text = (TEMPLATES_DIR / "hl_logo.svg").read_text(encoding="utf-8")

    assert "<svg" in text and "viewBox" in text
