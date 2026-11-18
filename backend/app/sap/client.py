"""SapClient: the only way the backend talks to SAP (invariant 5).

It speaks the mock's OData v2 service `ZHL_MM_MATERIAL_SRV` like a client of a real SAP
Gateway: Basic auth, the CSRF handshake before a `POST` (fetch the token on a `GET`, send it
back with the session cookie, fetch again once if SAP answers `x-csrf-token: Required`),
`{"d": ...}` payloads, `/Date(ms)/` dates and SAP error bodies.

A reservation is never retried after a timeout: the number may have been issued, and a
second `POST` would issue another one.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from types import TracebackType
from typing import Any, Literal

import httpx

from app.core.config import Settings

SERVICE_ROOT = "/sap/opu/odata/sap/ZHL_MM_MATERIAL_SRV"
CSRF_HEADER = "x-csrf-token"
DEFAULT_TIMEOUT_S = 10.0
MATERIAL_TYPES = {"glass_bead": "GLASS_BEAD", "charm": "CHARM"}
_DATE = re.compile(r"/Date\((-?\d+)\)/")


@dataclass(frozen=True)
class SapMaterial:
    sku: str
    material_number: str  # 18 digits, as SAP stores it
    description: str
    material_type: str
    family: str
    collection: str
    status: str
    color: str
    finish: str
    main_dimension_mm: float
    revision: str
    created_on: date | None
    created_by: str

    @property
    def material(self) -> str:
        """The material number as people read it: without leading zeros (GEN-04)."""
        return self.material_number.lstrip("0") or "0"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["created_on"] = self.created_on.isoformat() if self.created_on else None
        data["material"] = self.material
        return data


class SapError(Exception):
    """SAP answered with an error, or could not be reached (`unavailable`)."""

    def __init__(self, status: int, code: str, message: str, *, unavailable: bool = False):
        super().__init__(f"{code}: {message}" if code else message)
        self.status = status
        self.code = code
        self.message = message
        self.unavailable = unavailable

    @property
    def not_found(self) -> bool:
        return self.status == 404


def _parse_date(value: str | None) -> date | None:
    match = _DATE.fullmatch(value or "")
    if not match:
        return None
    return datetime.fromtimestamp(int(match.group(1)) / 1000, UTC).date()


def _material(entity: dict[str, Any]) -> SapMaterial:
    return SapMaterial(
        sku=entity["Sku"],
        material_number=entity["MaterialNumber"],
        description=entity["Description"],
        material_type=entity["MaterialType"],
        family=entity.get("Family", ""),
        collection=entity.get("Collection", ""),
        status=entity["Status"],
        color=entity.get("Color", ""),
        finish=entity.get("Finish", ""),
        main_dimension_mm=float(entity.get("MainDimensionMm") or 0),
        revision=entity.get("CurrentRevision", ""),
        created_on=_parse_date(entity.get("CreatedOn")),
        created_by=entity.get("CreatedBy", ""),
    )


def _literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


class SapClient:
    """Use as a context manager, or call `close()`."""

    def __init__(
        self,
        base_url: str,
        user: str,
        password: str,
        *,
        timeout: float = DEFAULT_TIMEOUT_S,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._http = httpx.Client(
            base_url=self._base_url + SERVICE_ROOT,
            auth=(user, password),
            timeout=timeout,
            transport=transport,
            headers={"accept": "application/json"},
        )
        self._csrf: str | None = None

    @classmethod
    def from_settings(cls, settings: Settings, **kwargs: Any) -> SapClient:
        return cls(
            settings.sap_base_url,
            settings.sap_user,
            settings.sap_password.get_secret_value(),
            **kwargs,
        )

    def __enter__(self) -> SapClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    # --- reads -----------------------------------------------------------------------

    def get_material(self, sku: str) -> SapMaterial:
        response = self._send("GET", f"/MaterialSet({_literal(sku)})")
        return _material(response.json()["d"])

    def list_materials(self, material_type: str | None = None) -> list[SapMaterial]:
        params = {}
        if material_type:
            params["$filter"] = f"MaterialType eq {_literal(material_type)}"
        response = self._send("GET", "/MaterialSet", params=params)
        return [_material(e) for e in response.json()["d"]["results"]]

    # --- the side effect -------------------------------------------------------------

    def reserve(
        self,
        kind: Literal["glass_bead", "charm"],
        description: str,
        created_by: str,
        *,
        family: str | None = None,
        collection: str | None = None,
    ) -> SapMaterial:
        """Reserve the next SKU and material number of the type (status `IN_DESIGN`)."""
        body = {
            "MaterialType": MATERIAL_TYPES[kind],
            "Description": description,
            "CreatedBy": created_by,
            "Family": family or "",
            "Collection": collection or "",
        }
        for attempt in range(2):
            token = self._csrf or self._fetch_token()
            response = self._send(
                "POST", "/MaterialSet", json=body, headers={CSRF_HEADER: token}, check=False
            )
            required = response.headers.get(CSRF_HEADER, "").lower() == "required"
            if response.status_code == 403 and required and attempt == 0:
                self._csrf = None  # session expired (or the mock restarted): fetch again
                continue
            self._raise_for(response)
            return _material(response.json()["d"])
        raise AssertionError("unreachable")  # pragma: no cover

    # --- transport -------------------------------------------------------------------

    def _fetch_token(self) -> str:
        response = self._send("GET", "", headers={CSRF_HEADER: "Fetch"})
        token = response.headers.get(CSRF_HEADER)
        if not token:
            raise SapError(response.status_code, "", "SAP sent no CSRF token")
        self._csrf = token
        return token

    def _send(
        self,
        method: str,
        path: str,
        *,
        check: bool = True,
        **kwargs: Any,
    ) -> httpx.Response:
        params = {"$format": "json", **kwargs.pop("params", {})}
        try:
            response = self._http.request(method, path, params=params, **kwargs)
        except httpx.TimeoutException as exc:
            raise SapError(0, "", f"SAP did not answer in time ({exc})", unavailable=True) from exc
        except httpx.HTTPError as exc:
            raise SapError(
                0, "", f"SAP is not reachable at {self._base_url}", unavailable=True
            ) from exc
        if check:
            self._raise_for(response)
        return response

    @staticmethod
    def _raise_for(response: httpx.Response) -> None:
        if response.is_success:
            return
        code, message = "", response.text.strip()[:200]
        try:
            error = response.json()["error"]
            code = error.get("code", "")
            message = error.get("message", {}).get("value", message)
        except (ValueError, KeyError, TypeError, AttributeError):
            pass
        raise SapError(
            response.status_code,
            code,
            message or f"HTTP {response.status_code}",
            unavailable=response.status_code in (502, 503, 504),
        )
