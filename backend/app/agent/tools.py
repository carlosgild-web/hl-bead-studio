"""The assistant's tools (PLAN §4). The model can read and propose; it cannot act.

- Read tools ask the deterministic validators (invariant 1), SAP through `SapClient`
  (invariant 5), the manual index, the geometry builders and the designs folder.
- `propose_parameters` fills the parameter panel; the designer can still edit it.
- The gated tools `request_reserve_sku`, `request_generate_design` and `request_render`
  check their arguments, store a pending action and return its id. The side effect happens
  only in `POST /api/actions/{id}/confirm`, after the designer's click (invariant 2).

A run opens at most one confirmation card per kind, so text that talks the model into
"reserve ten SKUs" ends with one card and nothing reserved (invariant 8).

Every tool returns a JSON-serializable dict: exactly what the model sees. Numbers in it come
from the validators, the geometry or SAP, so the model can quote them (invariant 3).
"""

from __future__ import annotations

import json
import logging
import uuid
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.core.config import Settings
from app.core.content import colors, finishes, materials
from app.core.paths import design_dir, design_file_names
from app.db.store import Store
from app.llm.base import ToolCall, ToolSpec
from app.render.jobs import RenderError, read_design
from app.render.presets import RenderPresetError, finish_options, resolve_finish
from app.render.runner import BLENDER_MISSING, blender_available
from app.sap import SapClient, SapError, SapMaterial
from app.standards.families import (
    FAMILY_CODES,
    Family,
    UnknownFamilyError,
    all_families,
    get_family,
)
from app.standards.identifiers import (
    InvalidIdentifierError,
    expected_revision,
    next_revision,
    revision_key,
    sku_kind,
    validate_revision,
    validate_sku,
)
from app.standards.manual_search import ManualIndex
from app.standards.naming import (
    COLLECTIONS,
    CatalogEntry,
    find_same_name,
    similar_names,
    validate_product_name,
)
from app.standards.validators import (
    ValidationResult,
    Violation,
    choice_label,
    validate_parameters,
)

logger = logging.getLogger(__name__)

FREE_TEXT_MAX = 200
NAME_MAX = 60
GATED_TOOLS = frozenset({"request_reserve_sku", "request_generate_design", "request_render"})
ACTION_OF_TOOL = {
    "request_reserve_sku": "reserve_sku",
    "request_generate_design": "generate_design",
    "request_render": "render",
}
AWAITING = (
    "A confirmation card is shown to the designer. Nothing has happened yet: it happens only "
    "if the designer clicks Confirm. Do not say it is done."
)


# --- previews ------------------------------------------------------------------------


class PreviewCache:
    """GLB previews built by `preview_geometry`, kept in memory for the viewer (LRU)."""

    def __init__(self, size: int = 32) -> None:
        self._items: OrderedDict[str, bytes] = OrderedDict()
        self._size = size
        self._lock = Lock()

    def put(self, glb: bytes) -> str:
        preview_id = uuid.uuid4().hex
        with self._lock:
            self._items[preview_id] = glb
            while len(self._items) > self._size:
                self._items.popitem(last=False)
        return preview_id

    def get(self, preview_id: str) -> bytes | None:
        with self._lock:
            return self._items.get(preview_id)


# --- context and results -------------------------------------------------------------


@dataclass
class ToolContext:
    settings: Settings
    store: Store
    sap: SapClient
    manual: ManualIndex
    previews: PreviewCache
    conversation_id: str
    run_id: int | None = None
    language: str = "en"
    opened_actions: dict[str, str] = field(default_factory=dict)  # kind -> action id


@dataclass(frozen=True)
class ToolResult:
    """`content` goes back to the model; `event` (optional) goes to the UI."""

    content: dict[str, Any]
    ok: bool = True
    event: dict[str, Any] | None = None

    def for_model(self) -> str:
        return json.dumps(self.content, ensure_ascii=False)


def _error(code: str, message: str, **extra: Any) -> ToolResult:
    return ToolResult({"error": {"code": code, "message": message, **extra}}, ok=False)


def _sap_error(exc: SapError) -> ToolResult:
    if exc.unavailable:
        return _error(
            "sap_unavailable",
            f"SAP is not available right now ({exc.message}). Nothing was checked or "
            "reserved in SAP; try again later.",
        )
    return _error("sap_error", f"SAP answered {exc.status} {exc.code}: {exc.message}")


def violation_dict(v: Violation, *, with_es: bool = False) -> dict[str, Any]:
    data: dict[str, Any] = {"rule": v.rule, "parameters": list(v.parameters), "message": v.message}
    if with_es:
        data["message_es"] = v.message_es or v.message
    if v.suggestions:
        data["nearest_valid"] = [
            {"parameter": s.parameter, "value": s.value} for s in v.suggestions
        ]
    return data


def validation_summary(result: ValidationResult, *, with_es: bool = False) -> dict[str, Any]:
    """The check as the agent and the panel see it. `with_es` adds `message_es` for the
    panel; the agent gets the English message only and answers in the designer's language."""
    return {
        "valid": result.ok,
        "family": result.family,
        "params": result.params,
        "violations": [violation_dict(v, with_es=with_es) for v in result.violations],
        "notes": result.notes,
        "rule_edition": result.rule_edition,
    }


# --- argument models -----------------------------------------------------------------


class _Args(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


def _family_field() -> Any:
    return Field(description="Family code: " + ", ".join(FAMILY_CODES))


class _ParamsMixin(BaseModel):
    @field_validator("params", mode="before", check_fields=False)
    @classmethod
    def _params_from_text(cls, value: Any) -> Any:
        """Small models sometimes send the object as a JSON string."""
        if isinstance(value, str):
            try:
                return json.loads(value)
            except ValueError:
                return value
        return value


class SearchManualArgs(_Args):
    query: str = Field(min_length=1, max_length=FREE_TEXT_MAX, description="Keywords or a rule id")
    language: Literal["en", "es", ""] = Field(default="", description="'en' or 'es'")


class NoArgs(_Args):
    pass


class FamilyArgs(_Args):
    code: str = Field(max_length=8, description="Family code: " + ", ".join(FAMILY_CODES))


class ParamsArgs(_Args, _ParamsMixin):
    family: str = _family_field()
    params: dict[str, Any] = Field(
        description="Parameter values by name (lengths in mm, as numbers), see describe_family"
    )


class CatalogArgs(_Args):
    name: str = Field(min_length=1, max_length=NAME_MAX, description="Proposed product name")
    family: str = Field(default="", max_length=8, description="Family code, for the full check")


class SkuArgs(_Args):
    sku: str = Field(max_length=16, description="SKU, e.g. GB-1002 or CH-2004")


class ReserveArgs(_Args):
    family: str = _family_field()
    name: str = Field(min_length=1, max_length=NAME_MAX, description="Product name (GEN-03)")
    collection: str = Field(default="", max_length=30, description=", ".join(COLLECTIONS))


# The Phase 7 eval saw a model offer revision I: the letters are in the tool definition.
REVISION_HELP = (
    "Design revision (GEN-02): A for the first, then B, C, D, E, F, G, H, J, K...; the "
    "letters I, O, Q, S, X and Z are never used"
)


class GenerateArgs(_Args, _ParamsMixin):
    sku: str = Field(max_length=16, description="SKU reserved in SAP, e.g. GB-1034")
    rev: str = Field(default="A", max_length=4, description=REVISION_HELP)
    family: str = Field(default="", max_length=8, description="Family code (default: SAP's)")
    params: dict[str, Any] = Field(description="The validated parameter values")


class RenderArgs(_Args):
    sku: str = Field(max_length=16, description="SKU of a generated design")
    rev: str = Field(default="A", max_length=4, description=REVISION_HELP)
    finish: str = Field(
        default="", max_length=30, description="Glass color or charm finish (default: the design's)"
    )


def _strip_titles(schema: Any) -> Any:
    if isinstance(schema, dict):
        return {k: _strip_titles(v) for k, v in schema.items() if k != "title"}
    if isinstance(schema, list):
        return [_strip_titles(v) for v in schema]
    return schema


def _schema(model: type[BaseModel]) -> dict[str, Any]:
    schema = _strip_titles(model.model_json_schema())
    schema.setdefault("properties", {})
    return schema


# --- helpers -------------------------------------------------------------------------


def _family(code: str) -> Family:
    return get_family(code.strip().upper())


def normalize_params(family: Family, params: dict[str, Any]) -> dict[str, Any]:
    """Parse values the model sent as text ("10", "true") by the schema's type. Parsing, not
    deciding: the validators still check every value."""
    out = dict(params)
    for name, value in params.items():
        prop = family.parameters.get(name, {})
        kind = prop.get("type")
        if not isinstance(value, str):
            continue
        text = value.strip().lower().removesuffix("mm").strip()
        try:
            if kind == "number":
                out[name] = float(text)
            elif kind == "integer" and float(text).is_integer():
                out[name] = int(float(text))
            elif kind == "boolean" and text in ("true", "false"):
                out[name] = text == "true"
        except ValueError:
            pass
    return out


def _catalog(sap: SapClient) -> list[CatalogEntry]:
    return [CatalogEntry(m.sku, m.description, m.status) for m in sap.list_materials()]


def generated_revisions(settings: Settings, sku: str) -> list[str]:
    """Revisions of a SKU that have files, oldest first."""
    folder = settings.designs_root / validate_sku(sku)
    if not folder.is_dir():
        return []
    revs = []
    for child in folder.iterdir():
        try:
            rev = validate_revision(child.name)
        except InvalidIdentifierError:
            continue
        if (child / design_file_names(sku, rev)["params"]).is_file():
            revs.append(rev)
    return sorted(revs, key=revision_key)


def _material_summary(m: SapMaterial) -> dict[str, Any]:
    return {
        "sku": m.sku,
        "sap_material": m.material,
        "name": m.description,
        "type": m.material_type,
        "family": m.family,
        "collection": m.collection,
        "status": m.status,
        "color": m.color,
        "finish": m.finish,
        "main_dimension_mm": m.main_dimension_mm,
        "current_revision": m.revision,
        "created_on": m.created_on.isoformat() if m.created_on else None,
    }


def _open_card(ctx: ToolContext, tool: str, payload: dict[str, Any], card: dict) -> ToolResult:
    kind = ACTION_OF_TOOL[tool]
    if kind in ctx.opened_actions:
        return _error(
            "card_already_open",
            f"A {kind} card is already open in this answer ({ctx.opened_actions[kind]}). One "
            "card per kind per answer; the designer decides on it first.",
        )
    action = ctx.store.create_action(ctx.conversation_id, kind, payload, run_id=ctx.run_id)
    ctx.opened_actions[kind] = action.id
    content = {"pending_action_id": action.id, "kind": kind, "status": "awaiting_confirmation"}
    content |= card | {"note": AWAITING}
    return ToolResult(content, event={"type": "pending_action", "action": action.to_dict()})


# --- read tools ----------------------------------------------------------------------


def search_design_manual(args: SearchManualArgs, ctx: ToolContext) -> ToolResult:
    lang = args.language or ctx.language
    passages = ctx.manual.search(args.query, lang=lang)
    return ToolResult({"passages": [p.to_dict() for p in passages]})


def list_families(args: NoArgs, ctx: ToolContext) -> ToolResult:
    return ToolResult(
        {
            "families": [
                {
                    "code": f.code,
                    "kind": f.kind,
                    "name": f.label[ctx.language],
                    "name_suffix": f.name_suffix,
                    "sku_prefix": f.sku_prefix,
                    "description": f.schema.get("description", ""),
                }
                for f in all_families()
            ]
        }
    )


def family_info(family: Family, language: str) -> dict[str, Any]:
    """A family's parameters (ranges, units, rule ids), defaults and colors or finishes, in
    one language. `describe_family` and `GET /api/families/{code}` return it."""
    params = {}
    for name, prop in family.parameters.items():
        entry = {k: prop[k] for k in ("type", "minimum", "maximum", "enum", "default") if k in prop}
        entry["label"] = prop.get("x-label", {}).get(language, name)
        entry["unit"] = prop.get("x-unit")
        entry["rules"] = prop.get("x-rule", [])
        entry["description"] = prop.get("description", "")
        if "pattern" in prop:
            entry["pattern"] = prop["pattern"]
        if "enum" in prop and not all(isinstance(v, int | float) for v in prop["enum"]):
            # How the panel shows each choice: "Gold plate", not gold_plate.
            entry["choices"] = {str(v): choice_label(name, v, prop, language) for v in prop["enum"]}
        params[name] = {k: v for k, v in entry.items() if v is not None}
    options = colors() if family.kind == "glass_bead" else finishes()
    material = materials()[family.material]
    return {
        "code": family.code,
        "kind": family.kind,
        "name": family.label[language],
        "name_suffix": family.name_suffix,
        "material": material["name"]["en"],
        "density_g_cm3": material["density_g_cm3"],
        "parameters": params,
        "defaults": family.defaults(),
        ("colors" if family.kind == "glass_bead" else "finishes"): {
            key: value["name"][language] for key, value in options.items()
        },
        "units": "All lengths are millimetres.",
    }


def describe_family(args: FamilyArgs, ctx: ToolContext) -> ToolResult:
    return ToolResult(family_info(_family(args.code), ctx.language))


def tool_validate_parameters(args: ParamsArgs, ctx: ToolContext) -> ToolResult:
    family = _family(args.family)
    result = validate_parameters(family.code, normalize_params(family, args.params))
    return ToolResult(validation_summary(result))


def build_preview(
    family: Family, params: dict[str, Any], previews: PreviewCache
) -> tuple[ValidationResult, dict[str, Any] | None]:
    """Validate, then build the model in memory and keep its GLB in `previews`. Returns the
    validation and, when the parameters are valid, the preview (id, url, measurements).
    Nothing is written to disk. `preview_geometry` and `POST /api/preview` use it."""
    from app.geometry import build_model
    from app.geometry.export import glb_bytes, measure

    result = validate_parameters(family.code, normalize_params(family, params))
    if not result.ok:
        return result, None
    model = build_model(family.code, result.params)
    measured = measure(model.shape, family.material).to_dict()
    preview_id = previews.put(glb_bytes(model.shape))
    preview = {
        "preview_id": preview_id,
        "url": f"/api/previews/{preview_id}.glb",
        "family": family.code,
        "params": result.params,
        "measurements": measured,
    }
    return result, preview


def preview_geometry(args: ParamsArgs, ctx: ToolContext) -> ToolResult:
    family = _family(args.family)
    result, preview = build_preview(family, args.params, ctx.previews)
    if preview is None:
        content = validation_summary(result)
        content["preview"] = "not built: the parameters break the manual"
        return ToolResult(content, ok=False)
    content = {
        "valid": True,
        "family": family.code,
        "params": result.params,
        "measurements": preview["measurements"],
        "preview_id": preview["preview_id"],
        "note": "Mass is before plating." if family.is_charm else "Mass of the glass.",
    }
    return ToolResult(content, event={"type": "preview", **preview})


def check_catalog(args: CatalogArgs, ctx: ToolContext) -> ToolResult:
    try:
        catalog = _catalog(ctx.sap)
    except SapError as exc:
        return _sap_error(exc)
    same = find_same_name(args.name, catalog)
    content: dict[str, Any] = {
        "name": args.name,
        "exists": same is not None,
        "existing": {"sku": same.sku, "name": same.name, "status": same.status} if same else None,
        "similar": [
            {"sku": e.sku, "name": e.name, "status": e.status}
            for e in similar_names(args.name, catalog)
            if e is not same
        ],
    }
    if args.family:
        violations = validate_product_name(args.name, _family(args.family), catalog)
        content["follows_GEN_03"] = not violations
        content["violations"] = [violation_dict(v) for v in violations]
    return ToolResult(content)


def sap_get_material(args: SkuArgs, ctx: ToolContext) -> ToolResult:
    sku = validate_sku(args.sku.upper())
    try:
        material = ctx.sap.get_material(sku)
    except SapError as exc:
        if exc.not_found:
            return ToolResult({"sku": sku, "exists": False})
        return _sap_error(exc)
    content = {"exists": True, **_material_summary(material)}
    content["generated_revisions"] = generated_revisions(ctx.settings, sku)
    return ToolResult(content)


def draft_catalog_text(args: SkuArgs, ctx: ToolContext) -> ToolResult:
    """The facts and the brand guidance for the catalog text; the model writes the text."""
    sku = validate_sku(args.sku.upper())
    try:
        material = ctx.sap.get_material(sku)
    except SapError as exc:
        if exc.not_found:
            return _error("unknown_sku", f"{sku} does not exist in SAP.")
        return _sap_error(exc)
    facts: dict[str, Any] = {
        "sku": sku,
        "name": material.description,
        "collection": material.collection or None,
    }
    revs = generated_revisions(ctx.settings, sku)
    if revs:
        record = read_design(ctx.settings, sku, revs[-1])
        family = get_family(record["family"])
        p = record["params"]
        facts["revision"] = revs[-1]
        facts["family"] = family.label[ctx.language]
        facts["dimensions_mm"] = {
            k: v for k, v in p.items() if family.parameters.get(k, {}).get("x-unit") == "mm"
        }
        facts["features"] = {
            k: v
            for k, v in p.items()
            if family.parameters.get(k, {}).get("x-unit") != "mm" and k not in ("color", "finish")
        }
        facts["mass_g"] = record["measurements"]["mass_g"]
        if family.kind == "glass_bead":
            facts["color"] = colors()[p["color"]]["name"][ctx.language]
            facts["material"] = "borosilicate glass"
        else:
            facts["finish"] = finishes()[p["finish"]]["name"][ctx.language]
            facts["material"] = "zinc alloy"
    else:
        facts["note"] = "No design files yet: only the SAP data is known."
        facts["main_dimension_mm"] = material.main_dimension_mm or None
    guide = ctx.manual.get("06-naming-and-collections#catalog-text", ctx.language)
    return ToolResult(
        {
            "facts": facts,
            "guidance": guide.text if guide else "",
            "source": "06-naming-and-collections#catalog-text",
            "note": "Write 1-2 sentences in the designer's language from these facts only; "
            "the designer approves the text.",
        }
    )


# --- UI tool -------------------------------------------------------------------------


def propose_parameters(args: ParamsArgs, ctx: ToolContext) -> ToolResult:
    family = _family(args.family)
    result = validate_parameters(family.code, normalize_params(family, args.params))
    summary = validation_summary(result)
    event = {"type": "parameter_proposal", "family": family.code, "validation": summary}
    return ToolResult(
        {"shown_in_parameter_panel": True, "editable_by_designer": True, **summary},
        event=event,
    )


# --- gated tools ---------------------------------------------------------------------


def request_reserve_sku(args: ReserveArgs, ctx: ToolContext) -> ToolResult:
    family = _family(args.family)
    collection = args.collection
    if collection and collection not in COLLECTIONS:
        return _error(
            "unknown_collection", f"{collection!r} is not a collection: {', '.join(COLLECTIONS)}"
        )
    try:
        catalog = _catalog(ctx.sap)
    except SapError as exc:
        return _sap_error(exc)
    violations = validate_product_name(args.name, family, catalog)
    if violations:
        return ToolResult(
            {
                "error": {"code": "invalid_name", "message": "The name breaks GEN-03."},
                "violations": [violation_dict(v) for v in violations],
            },
            ok=False,
        )
    payload = {
        "kind": family.kind,
        "family": family.code,
        "name": args.name,
        "collection": collection or None,
    }
    card = {"sku_type": family.sku_prefix, "name": args.name, "collection": collection or None}
    return _open_card(ctx, "request_reserve_sku", payload, card)


def request_generate_design(args: GenerateArgs, ctx: ToolContext) -> ToolResult:
    sku = validate_sku(args.sku.upper())
    rev = validate_revision(args.rev.upper())
    try:
        material = ctx.sap.get_material(sku)
    except SapError as exc:
        if exc.not_found:
            return _error("unknown_sku", f"{sku} does not exist in SAP; reserve a SKU first.")
        return _sap_error(exc)
    if material.status == "DISCONTINUED":
        return _error("discontinued", f"{sku} is discontinued; it gets no new revisions.")
    code = args.family or material.family
    if not code:
        return _error("family_unknown", f"SAP has no family for {sku}; give the family code.")
    family = _family(code)
    if material.family and material.family != family.code:
        return _error(
            "family_mismatch", f"{sku} is a {material.family} product in SAP, not {family.code}."
        )
    if sku_kind(sku) != family.kind:
        return _error("family_mismatch", f"{sku} is a {sku_kind(sku)} SKU; {family.code} is not.")
    folder = design_dir(ctx.settings.designs_root, sku, rev)
    if folder.exists() and any(folder.iterdir()):
        revs = generated_revisions(ctx.settings, sku)
        return _error(
            "revision_exists",
            f"{sku} revision {rev} already has files; files are never overwritten.",
            next_revision=next_revision(max([rev, *revs], key=revision_key)),
        )
    expected = expected_revision(generated_revisions(ctx.settings, sku), material.revision)
    if rev != expected:
        return _error(
            "revision_out_of_sequence",
            f"The next revision of {sku} is {expected}; revisions never skip a letter "
            f"(GEN-02), so {rev} is not possible yet.",
            next_revision=expected,
        )
    result = validate_parameters(family.code, normalize_params(family, args.params))
    if not result.ok:
        content = validation_summary(result)
        content["error"] = {"code": "invalid_parameters", "message": "Fix the violations first."}
        return ToolResult(content, ok=False)
    payload = {
        "sku": sku,
        "rev": rev,
        "family": family.code,
        "params": result.params,
        "name": material.description,
        "sap_material": material.material,
    }
    card = {"sku": sku, "rev": rev, "family": family.code, "name": material.description}
    return _open_card(ctx, "request_generate_design", payload, card)


def request_render(args: RenderArgs, ctx: ToolContext) -> ToolResult:
    sku = validate_sku(args.sku.upper())
    rev = validate_revision(args.rev.upper())
    try:
        record = read_design(ctx.settings, sku, rev)
    except RenderError as exc:
        return _error("not_generated", str(exc))
    if not blender_available(ctx.settings):
        return _error("renders_unavailable", BLENDER_MISSING)
    kind = get_family(record["family"]).kind
    try:
        finish = resolve_finish(kind, record["params"], args.finish or None)
    except RenderPresetError as exc:
        return _error("invalid_finish", str(exc), options=finish_options(kind))
    payload = {"sku": sku, "rev": rev, "finish": finish}
    return _open_card(ctx, "request_render", payload, dict(payload))


# --- registry ------------------------------------------------------------------------


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args: type[BaseModel]
    run: Callable[[Any, ToolContext], ToolResult]

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(self.name, self.description, _schema(self.args))


TOOLS: tuple[Tool, ...] = (
    Tool(
        "search_design_manual",
        "Search the Product Design Manual. Returns passages with their rule ids to cite.",
        SearchManualArgs,
        search_design_manual,
    ),
    Tool("list_families", "List the seven product families.", NoArgs, list_families),
    Tool(
        "describe_family",
        "Parameters of one family: units, ranges, defaults, rule ids, colors or finishes.",
        FamilyArgs,
        describe_family,
    ),
    Tool(
        "validate_parameters",
        "Check parameters against the manual. Returns every violation with its rule id and "
        "the nearest valid values. This check decides; do not override it.",
        ParamsArgs,
        tool_validate_parameters,
    ),
    Tool(
        "preview_geometry",
        "Build the 3D model in memory for valid parameters: volume, mass, bounding box and a "
        "preview in the viewer. Writes no files.",
        ParamsArgs,
        preview_geometry,
    ),
    Tool(
        "check_catalog",
        "Is a product name free in the catalog (SAP)? Lists similar products. With the "
        "family it also checks the naming pattern GEN-03.",
        CatalogArgs,
        check_catalog,
    ),
    Tool(
        "sap_get_material",
        "Status and data of a SKU in SAP, and its generated revisions.",
        SkuArgs,
        sap_get_material,
    ),
    Tool(
        "propose_parameters",
        "Fill the parameter panel with a proposal (validated). The designer can edit it.",
        ParamsArgs,
        propose_parameters,
    ),
    Tool(
        "request_reserve_sku",
        "Ask the designer to confirm reserving a new SKU and SAP material for a product name. "
        "Opens a confirmation card; nothing is reserved until the designer confirms.",
        ReserveArgs,
        request_reserve_sku,
    ),
    Tool(
        "request_generate_design",
        "Ask the designer to confirm generating STEP, STL, GLB and the drawing PDF for a "
        "reserved SKU. Opens a confirmation card; no files are written until confirmed.",
        GenerateArgs,
        request_generate_design,
    ),
    Tool(
        "request_render",
        "Ask the designer to confirm queuing a catalog render of a generated design. Opens "
        "a confirmation card; nothing is queued until confirmed.",
        RenderArgs,
        request_render,
    ),
    Tool(
        "draft_catalog_text",
        "Facts and brand guidance for the catalog description of a SKU; you write the text.",
        SkuArgs,
        draft_catalog_text,
    ),
)


class ToolRegistry:
    def __init__(self, tools: tuple[Tool, ...] = TOOLS) -> None:
        self._tools = {t.name: t for t in tools}

    @property
    def specs(self) -> list[ToolSpec]:
        return [t.spec for t in self._tools.values()]

    @property
    def names(self) -> list[str]:
        return list(self._tools)

    def execute(self, call: ToolCall, ctx: ToolContext) -> ToolResult:
        """Run one call. Never raises for bad input: the model gets an error to act on."""
        tool = self._tools.get(call.name)
        if tool is None:
            return _error("unknown_tool", f"There is no tool {call.name!r}.", tools=self.names)
        if "__invalid__" in call.arguments:
            return _error("invalid_arguments", "The arguments were not valid JSON.")
        try:
            args = tool.args.model_validate(call.arguments)
        except ValidationError as exc:
            problems = [
                f"{'.'.join(str(p) for p in e['loc']) or 'arguments'}: {e['msg']}"
                for e in exc.errors()
            ]
            return _error("invalid_arguments", "; ".join(problems))
        try:
            return tool.run(args, ctx)
        except UnknownFamilyError as exc:
            return _error("unknown_family", str(exc))
        except InvalidIdentifierError as exc:
            return _error("invalid_identifier", str(exc))
        except Exception as exc:  # a tool bug must not end the run; the trace keeps it
            logger.exception("tool %s failed", call.name)
            return _error("tool_failed", f"{call.name} failed: {exc.__class__.__name__}: {exc}")
