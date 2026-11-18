"""The parameter panel's routes: family schemas, live validation and the 3D preview.

All read-only. The panel asks the same validators the assistant asks (invariant 1), and a
preview is built in memory like `preview_geometry`: nothing is written under `DESIGNS_ROOT`.
"""

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agent.tools import build_preview, family_info, normalize_params, validation_summary
from app.api.deps import PreviewsDep
from app.core.content import colors, finishes, materials
from app.standards.families import Family, UnknownFamilyError, all_families, get_family
from app.standards.validators import validate_parameters

router = APIRouter(prefix="/api", tags=["families"])

Language = Literal["en", "es"]
MAX_PARAMS = 16


class ParamsBody(BaseModel):
    family: str = Field(max_length=8)
    params: dict[str, Any] = Field(max_length=MAX_PARAMS)


def _family_or_404(code: str) -> Family:
    try:
        return get_family(code.strip().upper())
    except UnknownFamilyError as exc:
        raise HTTPException(404, str(exc)) from exc


def _swatches(family: Family, lang: Language) -> list[dict[str, Any]]:
    """Colors (beads) or finishes (charms) with the hex the 3D viewer paints."""
    options = colors() if family.kind == "glass_bead" else finishes()
    return [
        {
            "id": key,
            "name": value["name"][lang],
            "hex": value["hex"],
            "transmission": value.get("transmission", 0.0),
            "metallic": value.get("metallic", 0.0),
            "roughness": value.get("roughness", 0.05),
        }
        for key, value in options.items()
    ]


@router.get("/families")
def list_families(lang: Language = "en") -> list[dict[str, Any]]:
    return [
        {"code": f.code, "kind": f.kind, "name": f.label[lang], "sku_prefix": f.sku_prefix}
        for f in all_families()
    ]


@router.get("/families/{code}")
def get_family_info(code: str, lang: Language = "en") -> dict[str, Any]:
    """Parameters in schema order, with ranges, steps, units and rule ids; the defaults; the
    colors or finishes with their hex."""
    family = _family_or_404(code)
    info = family_info(family, lang)
    for name, prop in family.parameters.items():
        if "x-step" in prop:
            info["parameters"][name]["step"] = prop["x-step"]
    info["material"] = materials()[family.material]["name"][lang]
    info["option_parameter"] = "color" if family.kind == "glass_bead" else "finish"
    info["swatches"] = _swatches(family, lang)
    info.pop(info["option_parameter"] + "s", None)
    return info


@router.post("/validate")
def validate(body: ParamsBody) -> dict[str, Any]:
    """The panel's live check: violations with rule ids and the nearest valid values."""
    family = _family_or_404(body.family)
    return validation_summary(
        validate_parameters(family.code, normalize_params(family, body.params))
    )


@router.post("/preview")
def preview(body: ParamsBody, previews: PreviewsDep) -> dict[str, Any]:
    """Build the model in memory after the designer edits the panel. Answers the validation
    and, when valid, the preview's GLB url and measurements."""
    family = _family_or_404(body.family)
    result, built = build_preview(family, body.params, previews)
    return {"validation": validation_summary(result), "preview": built}
