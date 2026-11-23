"""The OData service `ZHL_MM_MATERIAL_SRV`: look up and reserve materials (SKUs).

Auth, CSRF and chaos are middleware (`security.py`, `chaos.py`); these handlers only speak
OData. Keys arrive as `MaterialSet('CH-2004')`; the quotes may be URL-encoded.
"""

import sqlite3
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app.config import Settings
from app.db import Database, ReservationError
from app.odata import (
    INVALID_REQUEST,
    MATERIAL_NOT_FOUND,
    SERVICE_ROOT,
    SapError,
    key_value,
    material_entity,
    parse_filter,
)

METADATA_XML = (Path(__file__).parent / "metadata.xml").read_text(encoding="utf-8")
ENTITY_SETS = ["MaterialSet"]
MATERIAL_FILTERS = {
    "MaterialType": "material_type",
    "Status": "status",
    "Family": "family",
    "Collection": "collection",
    "Description": "description",
}

router = APIRouter(prefix=SERVICE_ROOT)


def get_db(request: Request) -> Database:
    return request.app.state.db


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


DbDep = Annotated[Database, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
FormatParam = Annotated[str | None, Query(alias="$format")]


def service_url(request: Request) -> str:
    """Absolute URL of the service root, for `__metadata.uri` and `Location`."""
    return str(request.base_url).rstrip("/") + SERVICE_ROOT


def check_format(fmt: str | None) -> None:
    if fmt is not None and fmt != "json":
        raise SapError(400, INVALID_REQUEST, "The mock only answers JSON: use $format=json")


class MaterialCreate(BaseModel):
    """Body of `POST MaterialSet`. SAP issues the SKU, material number, status and revision.

    Description is the product name, stored as sent (40 characters, like SAP's MAKTX).
    The company naming rules (GEN-03) are checked by the backend before it calls SAP.
    """

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    MaterialType: str = Field(min_length=1, max_length=10)
    Description: str = Field(min_length=1, max_length=40)
    CreatedBy: str = Field(min_length=1, max_length=40)
    Family: str | None = Field(default=None, max_length=3)
    Collection: str | None = Field(default=None, max_length=20)


# --- service document and metadata ----------------------------------------------------


@router.get("")
@router.get("/", include_in_schema=False)
def service_document(fmt: FormatParam = None) -> dict:
    """The service document; clients also call it to fetch a CSRF token."""
    check_format(fmt)
    return {"d": {"EntitySets": ENTITY_SETS}}


@router.get("/$metadata")
def metadata() -> Response:
    return Response(content=METADATA_XML, media_type="application/xml")


# --- materials -------------------------------------------------------------------------


@router.get("/MaterialSet")
def list_materials(
    request: Request,
    db: DbDep,
    filter_: Annotated[str | None, Query(alias="$filter")] = None,
    top: Annotated[int | None, Query(alias="$top", ge=0)] = None,
    skip: Annotated[int, Query(alias="$skip", ge=0)] = 0,
    fmt: FormatParam = None,
) -> dict:
    check_format(fmt)
    filters = parse_filter(filter_, MATERIAL_FILTERS) if filter_ is not None else {}
    base = service_url(request)
    rows = db.list_materials(filters, top=top, skip=skip)
    return {"d": {"results": [material_entity(r, base) for r in rows]}}


@router.get("/MaterialSet('{sku}')")
def get_material(request: Request, sku: str, db: DbDep, fmt: FormatParam = None) -> dict:
    check_format(fmt)
    return {"d": material_entity(_material_or_404(db, key_value(sku)), service_url(request))}


@router.post("/MaterialSet", status_code=201)
def reserve_material(
    request: Request,
    response: Response,
    payload: MaterialCreate,
    db: DbDep,
    settings: SettingsDep,
) -> dict:
    """Reserve the next SKU of the material type and the next material number."""
    try:
        sku = db.reserve(
            payload.MaterialType,
            payload.Description,
            payload.CreatedBy,
            settings.today(),
            family=payload.Family or None,
            collection=payload.Collection or None,
        )
    except ReservationError as exc:
        raise SapError(400, exc.code, exc.message) from exc
    entity = material_entity(_material_or_404(db, sku), service_url(request))
    response.headers["Location"] = entity["__metadata"]["uri"]
    return {"d": entity}


class MaterialUpdate(BaseModel):
    """Body of `MERGE MaterialSet('...')`: only the current revision can change."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    CurrentRevision: str = Field(min_length=1, max_length=2)


@router.api_route("/MaterialSet('{sku}')", methods=["MERGE", "PATCH"], status_code=204)
def update_material(sku: str, payload: MaterialUpdate, db: DbDep) -> Response:
    """OData v2 MERGE (or PATCH): set the current revision. 204 with no body, as SAP."""
    try:
        found = db.set_revision(key_value(sku), payload.CurrentRevision)
    except ReservationError as exc:
        raise SapError(400, exc.code, exc.message) from exc
    if not found:
        raise SapError(404, MATERIAL_NOT_FOUND, f"Material {key_value(sku)} does not exist")
    return Response(status_code=204)


def _material_or_404(db: Database, sku: str) -> sqlite3.Row:
    row = db.get_material(sku)
    if row is None:
        raise SapError(404, MATERIAL_NOT_FOUND, f"Material {sku} does not exist")
    return row
