"""An in-memory stand-in for the mock SAP service, as an httpx transport.

It answers like `sap-mock/` (OData v2 payloads, Basic auth, the CSRF handshake, SAP error
bodies), starts from the same seed file, and records every request, so the backend tests,
the Playwright server and the agent eval (`app.eval`) run without starting the second
service. `down = True` answers 503 like a maintenance window. Nothing in the app's
request path uses it: the app talks to `SAP_BASE_URL`.
"""

from __future__ import annotations

import base64
import json
import re
from datetime import UTC, date, datetime
from typing import Any

import httpx

from app.core.config import REPO_ROOT
from app.sap import SapClient

SEED = REPO_ROOT / "sap-mock" / "seed" / "materials.json"
ROOT = "/sap/opu/odata/sap/ZHL_MM_MATERIAL_SRV"
PREFIX = {"GLASS_BEAD": "GB", "CHARM": "CH"}


def _error(status: int, code: str, message: str, headers=None) -> httpx.Response:
    body = {"error": {"code": code, "message": {"lang": "en", "value": message}}}
    return httpx.Response(status, json=body, headers=headers)


class InMemorySap:
    def __init__(self, today: date = date(2026, 11, 18)) -> None:
        seed = json.loads(SEED.read_text(encoding="utf-8"))["materials"]
        self.materials: dict[str, dict[str, Any]] = {m["Sku"]: dict(m) for m in seed}
        self.today = today
        self.down = False
        self.token = "tok-1"
        self.requests: list[httpx.Request] = []

    @property
    def reservations(self) -> list[httpx.Request]:
        return [r for r in self.requests if r.method == "POST"]

    def client(self) -> SapClient:
        return SapClient("http://sap", "demo", "demo", transport=httpx.MockTransport(self))

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.down:
            return _error(503, "ZHL_GW/003", "SAP system is in maintenance; try again later")
        expected = "Basic " + base64.b64encode(b"demo:demo").decode()
        if request.headers.get("authorization") != expected:
            return _error(401, "ZHL_GW/001", "Logon failed")
        path = request.url.path.removeprefix(ROOT)
        if request.method == "GET":
            headers = {}
            if request.headers.get("x-csrf-token", "").lower() == "fetch":
                headers["x-csrf-token"] = self.token
            if path in ("", "/"):
                return httpx.Response(
                    200, json={"d": {"EntitySets": ["MaterialSet"]}}, headers=headers
                )
            match = re.fullmatch(r"/MaterialSet\('((?:[^']|'')*)'\)", path)
            if match:
                row = self.materials.get(match.group(1).replace("''", "'"))
                if row is None:
                    return _error(404, "ZHL_MM/001", f"Material {match.group(1)} does not exist")
                return httpx.Response(200, json={"d": self._entity(row)})
            if path == "/MaterialSet":
                rows = list(self.materials.values())
                flt = request.url.params.get("$filter")
                if flt:
                    wanted = re.fullmatch(r"MaterialType eq '(\w+)'", flt).group(1)
                    rows = [r for r in rows if r["MaterialType"] == wanted]
                return httpx.Response(200, json={"d": {"results": [self._entity(r) for r in rows]}})
            return _error(404, "ZHL_GW/006", "Resource not found")
        if request.method == "POST" and path == "/MaterialSet":
            if request.headers.get("x-csrf-token") != self.token:
                return _error(
                    403,
                    "ZHL_GW/002",
                    "CSRF token validation failed",
                    headers={"x-csrf-token": "Required"},
                )
            return self._reserve(json.loads(request.content))
        return _error(405, "ZHL_GW/005", "Method not allowed")

    def _reserve(self, body: dict[str, Any]) -> httpx.Response:
        prefix = PREFIX[body["MaterialType"]]
        numbers = [int(s[3:]) for s in self.materials if s.startswith(prefix)]
        sku = f"{prefix}-{max(numbers) + 1}"
        material = max(int(m["MaterialNumber"]) for m in self.materials.values()) + 1
        row = {
            "Sku": sku,
            "MaterialNumber": f"{material:018d}",
            "Description": body["Description"],
            "MaterialType": body["MaterialType"],
            "Family": body.get("Family") or None,
            "Collection": body.get("Collection") or None,
            "Status": "IN_DESIGN",
            "Color": None,
            "Finish": None,
            "MainDimensionMm": None,
            "Revision": "A",
            "CreatedOn": self.today.isoformat(),
            "CreatedBy": body["CreatedBy"],
        }
        self.materials[sku] = row
        return httpx.Response(201, json={"d": self._entity(row)})

    @staticmethod
    def _entity(row: dict[str, Any]) -> dict[str, Any]:
        day = date.fromisoformat(row["CreatedOn"])
        ms = int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp() * 1000)
        return {
            "Sku": row["Sku"],
            "MaterialNumber": row["MaterialNumber"],
            "Description": row["Description"],
            "MaterialType": row["MaterialType"],
            "Family": row.get("Family") or "",
            "Collection": row.get("Collection") or "",
            "Status": row["Status"],
            "Color": row.get("Color") or "",
            "Finish": row.get("Finish") or "",
            "MainDimensionMm": f"{row.get('MainDimensionMm') or 0:.1f}",
            "BaseUnit": "EA",
            "CurrentRevision": row.get("Revision") or "",
            "CreatedOn": f"/Date({ms})/",
            "CreatedBy": row["CreatedBy"],
        }
