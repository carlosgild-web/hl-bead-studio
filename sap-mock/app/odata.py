"""OData v2 conventions of an SAP Gateway service: payload shape, dates, keys, errors, $filter.

Only the subset Bead Studio needs. Error codes are invented for the mock (message class
`ZHL_GW` for the gateway, `ZHL_MM` for the material service); the table is in
`sap-mock/README.md`.
"""

import re
import sqlite3
import uuid
from collections.abc import Mapping
from datetime import UTC, date, datetime

from fastapi.responses import JSONResponse

SERVICE_NAME = "ZHL_MM_MATERIAL_SRV"
SERVICE_ROOT = f"/sap/opu/odata/sap/{SERVICE_NAME}"

# Gateway errors
LOGON_FAILED = "ZHL_GW/001"
CSRF_FAILED = "ZHL_GW/002"
MAINTENANCE = "ZHL_GW/003"
BACKEND_UNAVAILABLE = "ZHL_GW/004"
INVALID_REQUEST = "ZHL_GW/005"
RESOURCE_NOT_FOUND = "ZHL_GW/006"
# Material service errors (ZHL_MM/010-014 come from db.ReservationError)
MATERIAL_NOT_FOUND = "ZHL_MM/001"


class SapError(Exception):
    """An error answered with the SAP Gateway error body."""

    def __init__(
        self, status: int, code: str, message: str, headers: Mapping[str, str] | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.headers = dict(headers or {})


def is_service_path(path: str) -> bool:
    return path == SERVICE_ROOT or path.startswith(SERVICE_ROOT + "/")


def error_body(code: str, message: str) -> dict:
    return {
        "error": {
            "code": code,
            "message": {"lang": "en", "value": message},
            "innererror": {
                "transactionid": uuid.uuid4().hex.upper(),
                "timestamp": datetime.now(UTC).strftime("%Y%m%d%H%M%S"),
                "errordetails": [
                    {"code": code, "message": message, "severity": "error", "target": ""}
                ],
            },
        }
    }


def error_response(
    status: int, code: str, message: str, headers: Mapping[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(error_body(code, message), status_code=status, headers=headers)


# --- values --------------------------------------------------------------------------


def odata_date(value: str | date) -> str:
    """`2026-11-17` -> `/Date(1763337600000)/` (milliseconds since 1970, UTC midnight)."""
    day = date.fromisoformat(value) if isinstance(value, str) else value
    ms = int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp() * 1000)
    return f"/Date({ms})/"


def odata_decimal(value: float | None) -> str:
    """Edm.Decimal travels as a string in OData v2 JSON; SAP numeric fields default to 0."""
    return f"{value or 0:.1f}"


def key_literal(value: str) -> str:
    """An OData string literal: `CH-2004` -> `'CH-2004'` (quotes doubled)."""
    return "'" + value.replace("'", "''") + "'"


def key_value(raw: str) -> str:
    """The inverse of `key_literal` for the text between the quotes."""
    return raw.replace("''", "'")


# --- entities ------------------------------------------------------------------------


def material_entity(row: sqlite3.Row, service_url: str) -> dict:
    """A Material entity. ABAP strings are never null: empty fields are ""."""
    uri = f"{service_url}/MaterialSet({key_literal(row['sku'])})"
    return {
        "__metadata": {"id": uri, "uri": uri, "type": f"{SERVICE_NAME}.Material"},
        "Sku": row["sku"],
        "MaterialNumber": row["material_number"],
        "Description": row["description"],
        "MaterialType": row["material_type"],
        "Family": row["family"] or "",
        "Collection": row["collection"] or "",
        "Status": row["status"],
        "Color": row["color"] or "",
        "Finish": row["finish"] or "",
        "MainDimensionMm": odata_decimal(row["main_dimension_mm"]),
        "BaseUnit": "EA",
        "CurrentRevision": row["revision"],
        "CreatedOn": odata_date(row["created_on"]),
        "CreatedBy": row["created_by"],
    }


# --- $filter -------------------------------------------------------------------------

_CLAUSE = re.compile(r"\s*(\w+)\s+eq\s+'((?:[^']|'')*)'\s*")
_AND = re.compile(r"and\b")


def parse_filter(expression: str, allowed: Mapping[str, str]) -> dict[str, str]:
    """`MaterialType eq 'CHARM' and Status eq 'ACTIVE'` -> {column: value}.

    Supports only `<Property> eq '<value>'` clauses joined with `and`, on the properties in
    `allowed` (property -> column). Anything else is a 400, like an unsupported expression
    in a real Gateway service.
    """
    result: dict[str, str] = {}
    pos = 0
    while True:
        match = _CLAUSE.match(expression, pos)
        if match is None:
            raise _bad_filter(expression)
        prop, value = match.group(1), key_value(match.group(2))
        if prop not in allowed:
            names = ", ".join(sorted(allowed))
            raise SapError(
                400, INVALID_REQUEST, f"Property '{prop}' can't be filtered. Use one of: {names}"
            )
        if allowed[prop] in result:
            raise _bad_filter(expression)
        result[allowed[prop]] = value
        pos = match.end()
        if pos == len(expression):
            return result
        conjunction = _AND.match(expression, pos)
        if conjunction is None:
            raise _bad_filter(expression)
        pos = conjunction.end()


def _bad_filter(expression: str) -> SapError:
    return SapError(
        400,
        INVALID_REQUEST,
        f"Invalid $filter '{expression}'. The mock supports <Property> eq '<value>' joined"
        " with 'and'",
    )
