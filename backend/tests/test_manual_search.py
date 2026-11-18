"""Manual search (FTS5) and the GEN-03 name check."""

import pytest

from app.core.content import MANUAL_DIR
from app.standards.families import get_family
from app.standards.manual_search import ManualIndex, fts_query, sections
from app.standards.naming import CatalogEntry, similar_names, validate_product_name


@pytest.fixture(scope="module")
def index() -> ManualIndex:
    return ManualIndex()


def test_both_languages_have_the_same_sections():
    for path in (MANUAL_DIR / "en").glob("*.md"):
        en = sections(path)
        es = sections(MANUAL_DIR / "es" / path.name)
        assert len(en) == len(es), path.name
        for (h_en, _), (h_es, _) in zip(en, es, strict=True):
            assert h_en.split()[0] == h_es.split()[0] or "-" not in h_en.split()[0], (h_en, h_es)


def test_every_rule_is_a_passage_in_both_languages(index):
    for rule in ("GEN-01", "GEN-02", "GEN-03", "GEN-04", "GB-01", "GB-07", "CH-02", "CH-08"):
        assert index.rule(rule, "en").lang == "en"
        assert index.rule(rule, "es").lang == "es"
    assert index.rule("CH-02").source == "05-rules-charms#CH-02"


def test_search_finds_the_loop_rule(index):
    found = index.search("charm loop too thin for jump rings", lang="en")
    assert "CH-02" in [p.rule for p in found]


def test_search_spanish(index):
    found = index.search("agujero del mandril", lang="es")
    assert found[0].rule == "GB-01" and found[0].lang == "es"


def test_rule_id_in_the_query_comes_first(index):
    assert index.search("what does ch-07 say")[0].rule == "CH-07"


def test_non_rule_sections_have_language_independent_ids(index):
    en = index.get("06-naming-and-collections#catalog-text", "en")
    es = index.get("06-naming-and-collections#catalog-text", "es")
    assert en and es and en.rule is None and "catálogo" in es.heading.lower()


@pytest.mark.parametrize("query", ['"', "AND OR NOT", "*", "loop) OR (", ""])
def test_search_never_fails_on_odd_text(index, query):
    index.search(query)
    assert '"' not in fts_query(query).replace('" OR "', "").strip('"')


# --- GEN-03 ---------------------------------------------------------------------------

CATALOG = [
    CatalogEntry("GB-1001", "Midnight Lagoon Round", "ACTIVE"),
    CatalogEntry("GB-1002", "Desert Sand Faceted", "ACTIVE"),
    CatalogEntry("GB-1020", "Old Rose Round", "DISCONTINUED"),
]


def test_valid_name():
    assert validate_product_name("Amber Glow Faceted", get_family("FAC"), CATALOG) == []


def test_duplicate_name_ignores_case_and_counts_discontinued():
    [v] = validate_product_name("Old Rose Round", get_family("RND"), CATALOG)
    assert v.rule == "GEN-03" and "GB-1020" in v.message
    pattern, same = validate_product_name("old rose round", get_family("RND"), CATALOG)
    assert "Title Case" in pattern.message and "GB-1020" in same.message


@pytest.mark.parametrize(
    "name, fragment",
    [
        ("Amber", "1 words"),
        ("A Very Long Amber Glow Faceted", "6 words"),
        ("amber Faceted", "Title Case"),
        ("Amber Glow", "family name 'Faceted'"),
        ("Amber Glow Round", "family name 'Faceted'"),
    ],
)
def test_pattern_violations(name, fragment):
    [v] = validate_product_name(name, get_family("FAC"), CATALOG)
    assert fragment in v.message


def test_missing_family_word_is_suggested():
    [v] = validate_product_name("Amber Glow", get_family("FAC"), CATALOG)
    assert v.suggestions[0].value == "Amber Glow Faceted"


def test_similar_names():
    found = similar_names("Midnight Tide Round", CATALOG)
    assert found[0].sku == "GB-1001"
