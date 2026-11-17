"""Phase 1 seed checks: the material master the mock SAP starts from."""

import json
import re
from pathlib import Path
from typing import Any

import pytest

SEED = Path(__file__).resolve().parents[1] / "seed" / "materials.json"
TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "cad" / "templates"

SKU = {"GLASS_BEAD": re.compile(r"^GB-1\d{3}$"), "CHARM": re.compile(r"^CH-2\d{3}$")}
FAMILIES = {
    "GLASS_BEAD": {"RND", "FAC", "LEN", "RON", "CUS"},
    "CHARM": {"CRS", "INI", "DSC", "CUS"},
}
STATUSES = {"IN_DESIGN", "ACTIVE", "DISCONTINUED"}
COLLECTIONS = {"Permanente", "Coastal Garden", "Amber Hollow"}
REVISION = re.compile(r"^(?:[A-HJ-NPRTUVWY])+$")  # GEN-02: no I, O, Q, S, X, Z
MATERIAL_MIN, MATERIAL_MAX = 50_000_000, 59_999_999

# The ten products of luna-hybrid-agent's catalog (backend/app/agent/business_seed.py).
LUNA = {
    "GB-1001": "Midnight Lagoon Round",
    "GB-1002": "Desert Sand Faceted",
    "GB-1014": "Opal Mist Swirl",
    "GB-1027": "Terracotta Sunrise",
    "GB-1033": "Deep Forest Lentil",
    "CH-2004": "Crescent Moon & Star",
    "CH-2011": "Tiny Honeybee",
    "CH-2019": "Birth Flower — Lotus",
    "CH-2026": "Desert Cactus",
    "CH-2033": "Script Initial (A-Z)",
}


@pytest.fixture(scope="module")
def materials() -> list[dict[str, Any]]:
    return json.loads(SEED.read_text(encoding="utf-8"))["materials"]


def number(sku: str) -> int:
    return int(sku.split("-")[1])


def test_seed_has_the_luna_catalog_plus_fictional_products(materials) -> None:
    by_sku = {m["Sku"]: m for m in materials}

    assert {sku: by_sku[sku]["Description"] for sku in LUNA} == LUNA
    assert all(by_sku[sku]["Source"] == "luna" for sku in LUNA)
    assert sum(m["Source"] == "fictional" for m in materials) >= 15


def test_skus_material_numbers_and_names_are_unique(materials) -> None:
    for key in ("Sku", "MaterialNumber"):
        assert len({m[key] for m in materials}) == len(materials), key
    assert len({m["Description"].casefold() for m in materials}) == len(materials)


def test_every_record_is_well_formed(materials) -> None:
    for m in materials:
        kind = m["MaterialType"]
        assert SKU[kind].match(m["Sku"]), m["Sku"]
        assert m["Family"] in FAMILIES[kind], m["Sku"]
        assert m["Status"] in STATUSES, m["Sku"]
        assert m["Collection"] in COLLECTIONS, m["Sku"]
        assert REVISION.match(m["Revision"]), m["Sku"]
        assert m["MainDimensionMm"] > 0, m["Sku"]
        # Glass beads have a color, charms a finish (GB-07, CH-05).
        if kind == "GLASS_BEAD":
            assert m["Color"] and m["Finish"] is None, m["Sku"]
        else:
            assert m["Finish"] and m["Color"] is None, m["Sku"]


def test_material_numbers_are_18_digit_finished_goods(materials) -> None:
    for m in materials:
        assert re.fullmatch(r"\d{18}", m["MaterialNumber"]), m["Sku"]
        assert MATERIAL_MIN <= int(m["MaterialNumber"]) <= MATERIAL_MAX, m["Sku"]


def test_highest_issued_numbers_match_the_plan(materials) -> None:
    # The next reservations are GB-1034, CH-2034 and material 50000134 (GEN-04).
    beads = [number(m["Sku"]) for m in materials if m["MaterialType"] == "GLASS_BEAD"]
    charms = [number(m["Sku"]) for m in materials if m["MaterialType"] == "CHARM"]

    assert max(beads) == 1033
    assert max(charms) == 2033
    assert max(int(m["MaterialNumber"]) for m in materials) == 50_000_133


def test_numbers_were_issued_in_date_order(materials) -> None:
    by_date = sorted(materials, key=lambda m: (m["CreatedOn"], m["MaterialNumber"]))

    assert [m["MaterialNumber"] for m in by_date] == sorted(m["MaterialNumber"] for m in materials)
    for kind in SKU:
        skus = [m["Sku"] for m in by_date if m["MaterialType"] == kind]
        assert skus == sorted(skus, key=number), kind


@pytest.mark.skipif(not TEMPLATES_DIR.is_dir(), reason="cad/templates is not in this checkout")
def test_colors_and_finishes_are_approved(materials) -> None:
    colors = {
        c["id"] for c in json.loads((TEMPLATES_DIR / "colors.json").read_text("utf-8"))["colors"]
    }
    finishes = {
        f["id"]
        for f in json.loads((TEMPLATES_DIR / "finishes.json").read_text("utf-8"))["finishes"]
    }

    for m in materials:
        assert (m["Color"] in colors) if m["Color"] else (m["Finish"] in finishes), m["Sku"]
