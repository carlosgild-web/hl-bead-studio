"""SKU (GEN-04) and design revision (GEN-02) formats.

These checks run before a SKU or a revision becomes a path segment (invariant 4), so they
are strict allow-lists, not clean-ups.
"""

import re
from typing import Literal

REVISION_LETTERS = "ABCDEFGHJKLMNPRTUVWY"  # GEN-02: never I, O, Q, S, X, Z
_REVISION = re.compile(rf"^[{REVISION_LETTERS}]{{1,2}}$")
_SKU = re.compile(r"^(?:GB-1\d{3}|CH-2\d{3})$")


class InvalidIdentifierError(ValueError):
    """A SKU or revision that does not follow GEN-02 / GEN-04."""


def validate_sku(sku: object) -> str:
    """Return the SKU unchanged if it is `GB-1NNN` or `CH-2NNN`, else raise."""
    if not isinstance(sku, str) or not _SKU.fullmatch(sku):
        raise InvalidIdentifierError(f"Invalid SKU {sku!r}: expected GB-1NNN or CH-2NNN (GEN-04)")
    return sku


def sku_kind(sku: str) -> Literal["glass_bead", "charm"]:
    return "glass_bead" if validate_sku(sku).startswith("GB-") else "charm"


def validate_revision(rev: object) -> str:
    """Return the revision unchanged if it is valid under GEN-02, else raise."""
    if not isinstance(rev, str) or not _REVISION.fullmatch(rev):
        raise InvalidIdentifierError(
            f"Invalid revision {rev!r}: one or two letters from {REVISION_LETTERS} (GEN-02)"
        )
    return rev


def next_revision(rev: str | None) -> str:
    """The revision after `rev` (`None` gives `A`): ... H, J, ... Y, AA, AB, ... YY."""
    if rev is None:
        return REVISION_LETTERS[0]
    validate_revision(rev)
    letters = REVISION_LETTERS
    if len(rev) == 1:
        index = letters.index(rev)
        return letters[index + 1] if index + 1 < len(letters) else letters[0] * 2
    first, second = (letters.index(c) for c in rev)
    if second + 1 < len(letters):
        return letters[first] + letters[second + 1]
    if first + 1 < len(letters):
        return letters[first + 1] + letters[0]
    raise InvalidIdentifierError(f"No revision after {rev!r}")
