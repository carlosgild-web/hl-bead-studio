"""Generating a revision: files, refusals, confined paths and the audit log."""

import json
from datetime import date
from pathlib import Path

import cadquery as cq
import pytest

from app.cli import main
from app.core.config import Settings
from app.core.paths import UnsafePathError, confined, design_dir
from app.db import read_audit
from app.designs import DesignError, InvalidDesignError, RevisionExistsError, generate_design
from app.standards.families import get_family
from app.standards.identifiers import InvalidIdentifierError

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def fac() -> dict:
    return json.loads((EXAMPLES / "fac_10mm.json").read_text(encoding="utf-8"))


def generate(settings: Settings, **kwargs):
    values = {"sku": "GB-1034", "rev": "A", "settings": settings, "on_date": date(2026, 11, 17)}
    return generate_design("FAC", fac(), **(values | kwargs))


def test_generates_every_deliverable(settings: Settings) -> None:
    design = generate(settings, name="Honey Glow Faceted", sap_material="50000134")

    folder = settings.designs_root / "GB-1034" / "A"
    assert design.folder == folder.resolve()
    assert sorted(p.name for p in folder.iterdir()) == [
        "GB-1034_A.glb",
        "GB-1034_A.step",
        "GB-1034_A.stl",
        "GB-1034_A_drawing.pdf",
        "params.json",
    ]
    record = json.loads((folder / "params.json").read_text(encoding="utf-8"))
    assert record["params"] == fac()
    assert record["rule_edition"] == "Edition 1 (2026-11)"
    assert record["measurements"]["mass_g"] == design.measurements["mass_g"]
    assert (folder / "GB-1034_A_drawing.pdf").read_bytes().startswith(b"%PDF")


def test_step_reopens_as_the_same_solid(settings: Settings) -> None:
    design = generate(settings)

    solid = cq.importers.importStep(str(design.files["step"])).val()

    assert solid.isValid()
    assert solid.Volume() == pytest.approx(design.measurements["volume_mm3"], rel=1e-4)


def test_writes_an_audit_row(settings: Settings) -> None:
    generate(settings)

    (row,) = read_audit(settings.data_dir, sku="GB-1034")
    assert row["action"] == "design.generated"
    assert row["rev"] == "A"
    assert row["details"]["family"] == "FAC"
    assert "GB-1034_A.step" in row["details"]["files"]


def test_never_overwrites_a_revision(settings: Settings) -> None:
    generate(settings)
    before = (settings.designs_root / "GB-1034" / "A" / "params.json").stat().st_mtime_ns

    with pytest.raises(RevisionExistsError):
        generate(settings)

    after = (settings.designs_root / "GB-1034" / "A" / "params.json").stat().st_mtime_ns
    assert before == after
    assert len(read_audit(settings.data_dir)) == 1


def test_invalid_parameters_write_nothing(settings: Settings) -> None:
    with pytest.raises(InvalidDesignError) as error:
        generate_design(
            "RND",
            {"diameter_mm": 4.0, "hole_mm": 1.5, "color": "amber"},
            sku="GB-1035",
            rev="A",
            settings=settings,
        )

    assert error.value.result.rules == ["GB-02"]
    assert not (settings.designs_root / "GB-1035").exists()
    assert read_audit(settings.data_dir) == []


def test_sku_must_match_the_product_type(settings: Settings) -> None:
    with pytest.raises(DesignError, match="charm"):
        generate_design(
            "CRS", get_family("CRS").defaults(), sku="GB-1036", rev="A", settings=settings
        )


@pytest.mark.parametrize(
    ("sku", "rev"),
    [("../GB-1034", "A"), ("GB-1034", "../A"), ("GB-1034", "I"), ("/etc", "A"), ("GB-1034", "A/B")],
)
def test_identifiers_are_validated_before_they_become_paths(
    settings: Settings, sku: str, rev: str
) -> None:
    with pytest.raises(InvalidIdentifierError):
        generate(settings, sku=sku, rev=rev)
    assert not settings.designs_root.exists() or not any(settings.designs_root.iterdir())


def test_confined_rejects_paths_that_leave_the_root(tmp_path: Path) -> None:
    root = tmp_path / "designs"

    assert confined(root, "GB-1034", "A") == (root / "GB-1034" / "A").resolve()
    for escape in (("..", "x"), ("GB-1034", "..", "..", "x"), (str(tmp_path.parent),)):
        with pytest.raises(UnsafePathError):
            confined(root, *escape)


def test_design_dir_layout(tmp_path: Path) -> None:
    assert design_dir(tmp_path, "CH-2034", "B") == (tmp_path / "CH-2034" / "B").resolve()


def test_no_staging_folder_is_left_behind(settings: Settings) -> None:
    generate(settings)

    assert [p.name for p in settings.designs_root.iterdir()] == ["GB-1034"]


# ---------------------------------------------------------------- CLI


def test_cli_generate_and_validate(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("app.cli.get_settings", lambda: settings)
    params = str(EXAMPLES / "fac_10mm.json")

    assert main(["validate", "--family", "FAC", "--params", params]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True

    code = main(
        [
            "generate",
            "--family",
            "FAC",
            "--params",
            params,
            "--sku",
            "GB-1034",
            "--rev",
            "A",
            "--date",
            "2026-11-17",
        ]
    )
    assert code == 0
    assert "GB-1034_A_drawing.pdf" in capsys.readouterr().out


def test_cli_reports_violations_with_suggestions(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("app.cli.get_settings", lambda: settings)
    params = str(EXAMPLES / "rnd_4mm_invalid.json")

    code = main(
        ["generate", "--family", "RND", "--params", params, "--sku", "GB-1035", "--rev", "A"]
    )

    assert code == 2
    err = capsys.readouterr().err
    assert "GB-02" in err and "hole_mm=1.0" in err and "diameter_mm=4.5" in err
