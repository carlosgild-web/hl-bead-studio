"""The read-only routes behind the UI: families, live validation, preview, catalog, design
files and the gallery. None of them reserves, writes or queues anything."""

import pytest

from app.core.config import Settings
from tests.agent_env import AgentEnv

FAC_10 = {
    "diameter_mm": 10.0,
    "facet_count": 16,
    "facet_rows": 2,
    "hole_mm": 1.5,
    "color": "amber",
}


@pytest.fixture
def env(designed: Settings):
    environment = AgentEnv(designed)
    yield environment
    environment.close()


def test_families_list_all_seven_in_the_asked_language(env) -> None:
    families = env.http.get("/api/families", params={"lang": "es"}).json()

    assert [f["code"] for f in families] == ["RND", "FAC", "LEN", "RON", "CRS", "INI", "DSC"]
    assert {f["kind"] for f in families} == {"glass_bead", "charm"}


def test_family_info_has_units_steps_rules_and_swatches(env) -> None:
    info = env.http.get("/api/families/fac", params={"lang": "en"}).json()

    diameter = info["parameters"]["diameter_mm"]
    assert diameter["unit"] == "mm"
    assert diameter["step"] == 0.1
    assert diameter["minimum"] < diameter["maximum"]
    assert info["option_parameter"] == "color"
    amber = next(s for s in info["swatches"] if s["id"] == "amber")
    assert amber["hex"] == "#c9822b"
    assert set(info["defaults"]) == set(info["parameters"])


def test_charm_family_offers_finishes(env) -> None:
    info = env.http.get("/api/families/CRS", params={"lang": "es"}).json()

    assert info["option_parameter"] == "finish"
    assert "Baño de oro" in [s["name"] for s in info["swatches"]]
    assert info["material"] == "Aleación de zinc (Zamak 3)"


def test_unknown_family_is_404(env) -> None:
    assert env.http.get("/api/families/XYZ").status_code == 404
    assert env.http.post("/api/validate", json={"family": "XYZ", "params": {}}).status_code == 404


def test_validate_reports_rule_ids_and_nearest_values(env) -> None:
    params = FAC_10 | {"hole_mm": 0.5}

    result = env.http.post("/api/validate", json={"family": "FAC", "params": params}).json()

    assert result["valid"] is False
    violation = next(v for v in result["violations"] if "hole_mm" in v["parameters"])
    assert violation["rule"].startswith("GB-")
    assert violation["nearest_valid"]


def test_validate_accepts_a_valid_design(env) -> None:
    result = env.http.post("/api/validate", json={"family": "FAC", "params": FAC_10}).json()

    assert result["valid"] is True
    assert result["violations"] == []


def test_preview_builds_a_glb_in_memory_only(env) -> None:
    before = sorted(p.name for p in env.settings.designs_root.iterdir())

    body = env.http.post("/api/preview", json={"family": "FAC", "params": FAC_10}).json()

    assert body["validation"]["valid"] is True
    preview = body["preview"]
    assert preview["measurements"]["mass_g"] > 0
    glb = env.http.get(preview["url"])
    assert glb.status_code == 200
    assert glb.content[:4] == b"glTF"
    assert sorted(p.name for p in env.settings.designs_root.iterdir()) == before


def test_preview_of_invalid_params_builds_nothing(env) -> None:
    params = FAC_10 | {"hole_mm": 0.5}

    body = env.http.post("/api/preview", json={"family": "FAC", "params": params}).json()

    assert body["validation"]["valid"] is False
    assert body["preview"] is None


def test_catalog_lists_sap_materials_with_generated_revisions(env) -> None:
    # GB-1034/A has files in the designs folder; give it a SAP record like a reservation.
    env.sap.materials["GB-1034"] = env.sap.materials["GB-1005"] | {
        "Sku": "GB-1034",
        "Description": "Cobalt Test Round",
        "Status": "IN_DESIGN",
    }

    items = env.http.get("/api/catalog").json()

    by_sku = {i["sku"]: i for i in items}
    assert by_sku["CH-2004"]["name"]
    assert by_sku["GB-1034"]["generated_revisions"] == ["A"]
    assert by_sku["CH-2004"]["generated_revisions"] == []
    assert by_sku["CH-2004"]["main_dimension_source"] == "sap"
    assert not env.sap.reservations  # read only


def test_a_new_sku_takes_its_size_from_the_generated_files(env) -> None:
    # A reservation has no main dimension in SAP; GB-1034/A has generated files.
    env.sap.materials["GB-1034"] = env.sap.materials["GB-1005"] | {
        "Sku": "GB-1034",
        "MainDimensionMm": None,
    }

    item = next(i for i in env.http.get("/api/catalog").json() if i["sku"] == "GB-1034")

    assert item["main_dimension_source"] == "design"
    assert 5 < item["main_dimension_mm"] < 30
    unknown = next(i for i in env.http.get("/api/catalog").json() if i["sku"] == "GB-1005")
    assert unknown["main_dimension_source"] == "sap"


def test_catalog_says_when_sap_is_down(env) -> None:
    env.sap.down = True

    response = env.http.get("/api/catalog")

    assert response.status_code == 502


def test_design_record_and_files(env) -> None:
    record = env.http.get("/api/designs/GB-1034/A").json()

    assert record["family"] == "RND"
    assert record["measurements"]["mass_g"] > 0
    pdf = env.http.get(record["urls"]["drawing"])
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content[:4] == b"%PDF"
    step = env.http.get(record["urls"]["step"])
    assert "attachment" in step.headers["content-disposition"]


def test_design_routes_reject_unsafe_identifiers(env) -> None:
    assert env.http.get("/api/designs/GB-1034/A/files/params").status_code == 422
    assert env.http.get("/api/designs/..%2F..%2Fetc/A").status_code in (404, 422)
    assert env.http.get("/api/designs/gb-99/A").status_code == 422
    assert env.http.get("/api/designs/GB-1099/A").status_code == 404


def test_gallery_lists_the_committed_renders(env) -> None:
    gallery = env.http.get("/api/gallery").json()

    assert gallery["renders"]
    first = gallery["renders"][0]
    image = env.http.get(first["url"])
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/webp"


def test_gallery_serves_only_manifest_files(env) -> None:
    assert env.http.get("/api/gallery/manifest.json").status_code == 404
    assert env.http.get("/api/gallery/..%2F..%2FREADME.md").status_code == 404


def test_every_violation_has_a_spanish_message() -> None:
    """Each `Violation(...)` in the rule code passes `message_es` (decision 0013, item 5)."""
    import ast

    from app.core.config import REPO_ROOT

    for path in ("app/standards/validators.py", "app/standards/naming.py"):
        tree = ast.parse((REPO_ROOT / "backend" / path).read_text(encoding="utf-8"))
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "Violation"
        ]
        assert calls, path
        missing = [c.lineno for c in calls if "message_es" not in {k.arg for k in c.keywords}]
        assert not missing, f"{path}: Violation without message_es at lines {missing}"


def test_the_panel_check_carries_the_spanish_message(env) -> None:
    params = FAC_10 | {"hole_mm": 0.5}

    result = env.http.post("/api/validate", json={"family": "FAC", "params": params}).json()

    hole = next(v for v in result["violations"] if "hole_mm" in v["parameters"])
    assert "not allowed" in hole["message"]
    assert "no está permitido" in hole["message_es"]


def test_suggest_name_fixes_what_was_typed() -> None:
    from app.standards.families import get_family
    from app.standards.naming import suggest_name

    fac = get_family("FAC")
    assert suggest_name("amber   glow", fac) == "Amber Glow Faceted"
    assert suggest_name("amber glow faceted", fac) == "Amber Glow Faceted"
    assert suggest_name("deep sea blue green", fac) == "Deep Sea Blue Faceted"
    assert suggest_name("  ", fac) is None


def test_name_check_while_typing(env) -> None:
    existing = env.sap.materials["GB-1005"]["Description"]

    def check(name: str, family: str = "FAC") -> dict:
        return env.http.post("/api/names/check", json={"family": family, "name": name}).json()

    free = check("Amber Glow Faceted")
    assert free["follows"] and free["violations"] == [] and free["suggestion"] is None

    typed = check("amber glow")
    assert not typed["follows"]
    assert typed["suggestion"] == "Amber Glow Faceted"
    assert all(v["rule"] == "GEN-03" and v["message_es"] for v in typed["violations"])

    taken = check(existing, "RND")
    assert not taken["follows"]
    assert any(
        "GB-1005" in v["message"] and "ya existe" in v["message_es"] for v in taken["violations"]
    )
    assert len(taken["similar"]) <= 3 and all(s["sku"] != "GB-1005" for s in taken["similar"])
    assert not env.sap.reservations  # read only


def test_name_check_without_sap_still_checks_the_pattern(env) -> None:
    env.sap.down = True

    body = env.http.post("/api/names/check", json={"family": "FAC", "name": "amber"}).json()

    assert body["sap_available"] is False
    assert not body["follows"] and body["suggestion"] == "Amber Faceted"
