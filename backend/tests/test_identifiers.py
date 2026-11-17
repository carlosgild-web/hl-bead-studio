"""GEN-02 revisions and GEN-04 SKUs: strict allow-lists (they become path segments)."""

import pytest

from app.standards.identifiers import (
    InvalidIdentifierError,
    next_revision,
    sku_kind,
    validate_revision,
    validate_sku,
)


@pytest.mark.parametrize("sku", ["GB-1034", "GB-1999", "CH-2004", "CH-2034"])
def test_valid_skus(sku: str) -> None:
    assert validate_sku(sku) == sku


@pytest.mark.parametrize(
    "sku",
    [
        "GB-2034",
        "CH-1034",
        "GB-103",
        "gb-1034",
        "GB-1034 ",
        "../GB-1034",
        "GB-1034/..",
        "",
        None,
        1034,
    ],
)
def test_invalid_skus(sku: object) -> None:
    with pytest.raises(InvalidIdentifierError):
        validate_sku(sku)


def test_sku_kind() -> None:
    assert sku_kind("GB-1034") == "glass_bead"
    assert sku_kind("CH-2034") == "charm"


@pytest.mark.parametrize("rev", ["A", "H", "J", "Y", "AA", "YY"])
def test_valid_revisions(rev: str) -> None:
    assert validate_revision(rev) == rev


@pytest.mark.parametrize("rev", ["I", "O", "Q", "S", "X", "Z", "a", "AAA", "", "A/", "..", "AI"])
def test_invalid_revisions(rev: str) -> None:
    with pytest.raises(InvalidIdentifierError):
        validate_revision(rev)


@pytest.mark.parametrize(
    ("rev", "expected"),
    [(None, "A"), ("A", "B"), ("H", "J"), ("N", "P"), ("R", "T"), ("Y", "AA"), ("AY", "BA")],
)
def test_next_revision_skips_confusable_letters(rev: str | None, expected: str) -> None:
    assert next_revision(rev) == expected


def test_the_sequence_ends_after_yy() -> None:
    with pytest.raises(InvalidIdentifierError):
        next_revision("YY")
