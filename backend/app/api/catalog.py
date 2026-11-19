"""The catalog view's routes: SAP materials with their generated revisions, the files of a
revision and the pre-generated render gallery (decision 0006).

All read-only. SAP is reached only through `SapClient` (invariant 5); every file path is
built from a validated SKU and revision and stays inside its root (invariant 4).
"""

import json
from functools import lru_cache
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.agent.tools import generated_revisions
from app.api.deps import SapFactoryDep, SettingsDep
from app.core.config import REPO_ROOT, Settings
from app.core.paths import UnsafePathError, confined, design_dir, design_file_names
from app.render.jobs import RenderError, read_design
from app.sap import SapError
from app.standards.identifiers import InvalidIdentifierError

router = APIRouter(prefix="/api", tags=["catalog"])

GALLERY_DIR = REPO_ROOT / "docs" / "gallery"
FileKind = Literal["step", "stl", "glb", "drawing"]
MEDIA_TYPES = {
    "step": "model/step",
    "stl": "model/stl",
    "glb": "model/gltf-binary",
    "drawing": "application/pdf",
}


@router.get("/catalog")
def catalog(settings: SettingsDep, sap_factory: SapFactoryDep) -> list[dict[str, Any]]:
    """Every SAP material, newest first, with the revisions that have files here."""
    try:
        with sap_factory() as sap:
            materials = sap.list_materials()
    except SapError as exc:
        raise HTTPException(502, f"SAP is not available: {exc}") from exc
    items = []
    for m in materials:
        revisions = generated_revisions(settings, m.sku)
        size, size_source = _main_dimension(settings, m.sku, m.main_dimension_mm, revisions)
        items.append(
            {
                "sku": m.sku,
                "sap_material": m.material,
                "name": m.description,
                "type": m.material_type,
                "family": m.family,
                "collection": m.collection,
                "status": m.status,
                "color": m.color,
                "finish": m.finish,
                "main_dimension_mm": size,
                "main_dimension_source": size_source,
                "current_revision": m.revision,
                "created_on": m.created_on.isoformat() if m.created_on else None,
                "created_by": m.created_by,
                "generated_revisions": revisions,
            }
        )
    items.sort(key=lambda i: (i["created_on"] or "", i["sku"]), reverse=True)
    return items


def _main_dimension(
    settings: Settings, sku: str, from_sap: float, revisions: list[str]
) -> tuple[float | None, Literal["sap", "design"] | None]:
    """SAP's main dimension, else the largest side of the newest generated revision's bounding
    box: a reservation is made before any parameters exist, so new SKUs have none in SAP."""
    if from_sap:
        return from_sap, "sap"
    for rev in reversed(revisions):
        try:
            bbox = read_design(settings, sku, rev).get("measurements", {}).get("bbox_mm")
        except (RenderError, InvalidIdentifierError, ValueError):
            continue
        if bbox:
            return round(max(float(v) for v in bbox), 1), "design"
    return None, None


@router.get("/designs/{sku}/{rev}")
def design(sku: str, rev: str, settings: SettingsDep) -> dict[str, Any]:
    """The record of a generated revision (`params.json`) with the url of each file."""
    try:
        record = read_design(settings, sku, rev)
    except InvalidIdentifierError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RenderError as exc:
        raise HTTPException(404, str(exc)) from exc
    record["urls"] = {kind: f"/api/designs/{sku}/{rev}/files/{kind}" for kind in MEDIA_TYPES}
    return record


@router.get("/designs/{sku}/{rev}/files/{kind}")
def design_file(sku: str, rev: str, kind: FileKind, settings: SettingsDep) -> FileResponse:
    try:
        path = design_dir(settings.designs_root, sku, rev) / design_file_names(sku, rev)[kind]
    except (InvalidIdentifierError, UnsafePathError) as exc:
        raise HTTPException(422, str(exc)) from exc
    if not path.is_file():
        raise HTTPException(404, f"{sku} revision {rev} has no {kind} file")
    inline = kind in ("drawing", "glb")
    return FileResponse(
        path,
        media_type=MEDIA_TYPES[kind],
        filename=path.name,
        content_disposition_type="inline" if inline else "attachment",
    )


@lru_cache
def _manifest() -> dict[str, Any]:
    path = GALLERY_DIR / "manifest.json"
    if not path.is_file():
        return {"renders": []}
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/gallery")
def gallery() -> dict[str, Any]:
    """The renders made locally with Blender and committed for the online demo."""
    manifest = _manifest()
    renders = [r | {"url": f"/api/gallery/{r['file']}"} for r in manifest.get("renders", [])]
    return {"generated_at": manifest.get("generated_at"), "renders": renders}


@router.get("/gallery/{file_name}")
def gallery_image(file_name: str) -> FileResponse:
    known = {r["file"] for r in _manifest().get("renders", [])}
    if file_name not in known:
        raise HTTPException(404, "not in the gallery")
    try:
        path = confined(GALLERY_DIR, file_name)
    except UnsafePathError as exc:
        raise HTTPException(404, "not in the gallery") from exc
    return FileResponse(path, media_type="image/webp")
