"""Generate the files of one design revision (manual 08-deliverables).

`generate_design` is the side effect behind the confirmation gate (invariant 2): Phase 5's
`POST /actions/{id}/confirm` and the CLI call it; the assistant never does. It validates the
parameters again, refuses to overwrite a revision, writes every file into a temporary folder
inside `DESIGNS_ROOT` and moves it into place in one step, then writes the audit row.
"""

import json
import shutil
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.core.content import colors, finishes, materials
from app.core.paths import confined, design_dir, design_file_names
from app.db import write_audit
from app.drawing import TitleBlock, drawing_scale, drawing_svg, svg_to_pdf
from app.geometry import build_model
from app.geometry.export import export_glb, export_step, export_stl, measure
from app.standards.families import Family, get_family
from app.standards.identifiers import sku_kind
from app.standards.rules import RULE_EDITION
from app.standards.validators import ValidationResult, validate_parameters


class DesignError(Exception):
    """The design cannot be generated; the message says why."""


class InvalidDesignError(DesignError):
    def __init__(self, result: ValidationResult):
        self.result = result
        rules = ", ".join(result.rules)
        super().__init__(f"The parameters break the manual ({rules}); nothing was generated.")


class RevisionExistsError(DesignError):
    """Files of a revision are never overwritten (manual 08-deliverables)."""


@dataclass(frozen=True)
class GeneratedDesign:
    sku: str
    rev: str
    family: str
    folder: Path
    files: dict[str, Path]
    measurements: dict[str, Any]
    drawing_scale: str
    validation: ValidationResult


def material_text(family: Family, params: dict[str, Any]) -> str:
    """Title block text: base material plus glass color (and rod code) or plating finish."""
    material = materials()[family.material]["name"]["en"]
    if family.is_charm:
        return f"{material}, {finishes()[params['finish']]['name']['en']}"
    color = colors()[params["color"]]
    return f"{material}, {color['name']['en']} ({color['supplier_code']})"


def generate_design(
    family_code: str,
    params: dict[str, Any],
    *,
    sku: str,
    rev: str,
    settings: Settings,
    name: str | None = None,
    sap_material: str | None = None,
    designer: str = "Product Design",
    actor: str = "cli",
    on_date: date | None = None,
) -> GeneratedDesign:
    family = get_family(family_code)
    folder = design_dir(settings.designs_root, sku, rev)  # validates SKU and revision
    if sku_kind(sku) != family.kind:
        raise DesignError(f"{sku} is a {sku_kind(sku)} SKU but {family.code} is a {family.kind}")
    result = validate_parameters(family.code, params)
    if not result.ok:
        raise InvalidDesignError(result)
    if folder.exists() and any(folder.iterdir()):
        raise RevisionExistsError(
            f"{sku} revision {rev} already has files; create the next revision"
        )

    p = result.params
    model = build_model(family.code, p)
    measured = measure(model.shape, family.material)
    names = design_file_names(sku, rev)
    today = (on_date or datetime.now(UTC).date()).isoformat()
    title = TitleBlock(
        name=name or "Name pending",
        sku=sku,
        rev=rev,
        sap_material=sap_material or "—",
        family=f"{family.label['en']} ({family.code})",
        material=material_text(family, p),
        mass=f"{measured.mass_g:.2f} g",
        date=today,
        designer=designer,
        file=names["step"],
        mass_label="MASS (BEFORE PLATING)" if family.is_charm else "MASS",
    )
    svg = drawing_svg(model, family.kind, title)

    root = settings.designs_root
    root.mkdir(parents=True, exist_ok=True)
    staging = confined(root, f".staging-{uuid.uuid4().hex}")
    staging.mkdir()
    try:
        export_step(model.shape, staging / names["step"])
        export_stl(model.shape, staging / names["stl"])
        export_glb(model.shape, staging / names["glb"])
        (staging / names["drawing"]).write_bytes(svg_to_pdf(svg))
        record = {
            "sku": sku,
            "rev": rev,
            "family": family.code,
            "name": title.name,
            "sap_material": sap_material,
            "params": p,
            "rule_edition": RULE_EDITION,
            "validation_notes": result.notes,
            "measurements": measured.to_dict(),
            "drawing_scale": drawing_scale(svg),
            "generated_on": today,
            "files": {k: v for k, v in names.items() if k != "params"},
        }
        (staging / names["params"]).write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        folder.parent.mkdir(parents=True, exist_ok=True)
        if folder.exists():
            folder.rmdir()  # empty (checked above)
        staging.rename(folder)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    files = {kind: folder / file_name for kind, file_name in names.items()}
    write_audit(
        settings.data_dir,
        "design.generated",
        actor=actor,
        sku=sku,
        rev=rev,
        details={
            "family": family.code,
            "files": sorted(names.values()),
            "mass_g": measured.mass_g,
            "rule_edition": RULE_EDITION,
        },
    )
    return GeneratedDesign(
        sku, rev, family.code, folder, files, measured.to_dict(), drawing_scale(svg), result
    )
