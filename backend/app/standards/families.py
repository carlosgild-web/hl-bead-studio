"""The seven product families, read from their JSON Schemas (`standards/schemas/`)."""

import json
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Literal

from app.core.content import SCHEMAS_DIR

FAMILY_CODES: tuple[str, ...] = ("RND", "FAC", "LEN", "RON", "CRS", "INI", "DSC")

Kind = Literal["glass_bead", "charm"]


class UnknownFamilyError(ValueError):
    """The family code is not one of the seven families."""


@dataclass(frozen=True)
class Family:
    code: str
    kind: Kind
    material: str
    sku_prefix: str
    name_suffix: str
    label: dict[str, str]
    schema: dict[str, Any] = field(repr=False, compare=False)

    @property
    def is_charm(self) -> bool:
        return self.kind == "charm"

    @property
    def parameters(self) -> dict[str, dict[str, Any]]:
        return self.schema["properties"]

    def defaults(self) -> dict[str, Any]:
        """The family's default design (valid by construction; covered by tests)."""
        return {name: prop["default"] for name, prop in self.parameters.items()}


@lru_cache
def get_family(code: str) -> Family:
    if code not in FAMILY_CODES:
        raise UnknownFamilyError(
            f"Unknown family {code!r}; expected one of {', '.join(FAMILY_CODES)}"
        )
    schema = json.loads((SCHEMAS_DIR / f"{code}.schema.json").read_text(encoding="utf-8"))
    meta = schema["x-family"]
    return Family(
        code=meta["code"],
        kind=meta["kind"],
        material=meta["material"],
        sku_prefix=meta["sku_prefix"],
        name_suffix=meta["name_suffix"],
        label=meta["label"],
        schema=schema,
    )


def all_families() -> list[Family]:
    return [get_family(code) for code in FAMILY_CODES]
