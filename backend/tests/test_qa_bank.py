"""The Q&A bank (decision 0022) stays true to the manual and to the app's checks."""

import re
from functools import cache

import pytest

from app.agent.loop import claims_a_card
from app.core.content import MANUAL_DIR, qa_bank
from app.standards.families import get_family
from app.standards.validators import validate_parameters

BANK = qa_bank()
ENTRIES = BANK.entries
RULE_ID = re.compile(r"\b(?:GB|CH|GEN)-\d{2}\b")
NUMBER = re.compile(r"(?<![\w.-])\d+(?:\.\d+)?(?![\w-])")
TEXTS = [(e, lang) for e in ENTRIES for lang in ("en", "es")]


def _id(value):
    if isinstance(value, tuple):
        return f"{value[0].id}-{value[1]}"
    return getattr(value, "id", None)


@cache
def manual_en() -> str:
    return "\n".join(
        p.read_text(encoding="utf-8") for p in sorted((MANUAL_DIR / "en").glob("*.md"))
    )


@cache
def manual_numbers() -> frozenset[str]:
    return frozenset(NUMBER.findall(manual_en()))


def test_ids_are_unique_and_kinds_known() -> None:
    ids = [e.id for e in ENTRIES]
    assert len(ids) == len(set(ids)) == 46
    assert set(BANK.kinds) == {"design", "knowledge", "howto", "guardrail"}


@pytest.mark.parametrize("entry", ENTRIES, ids=_id)
def test_rules_exist_and_are_cited_in_both_languages(entry) -> None:
    known = set(RULE_ID.findall(manual_en()))
    assert set(entry.rules) <= known
    assert set(entry.expect.rules) <= known
    if entry.kind != "design":
        for lang in ("en", "es"):
            answer = entry.text(lang).answer
            assert all(rule in answer for rule in entry.rules), (lang, entry.rules)


def _numbers_to_check(entry) -> list[str]:
    answer = entry.en.answer
    if entry.id == "guard-engraving-injection":
        # The character count of the quoted injection text is computed, not in the manual.
        quoted = re.search(r'"([^"]+)"', answer)
        assert quoted, "the answer quotes the engraved text"
        count = str(len(quoted.group(1)))
        assert count in NUMBER.findall(answer)
        answer = answer.replace(quoted.group(0), "")
        return [n for n in NUMBER.findall(answer) if n != count]
    return NUMBER.findall(answer)


@pytest.mark.parametrize("entry", [e for e in ENTRIES if e.kind in ("knowledge", "howto")], ids=_id)
def test_every_number_in_an_english_answer_is_in_the_manual(entry) -> None:
    missing = [n for n in _numbers_to_check(entry) if n not in manual_numbers()]
    assert not missing, f"not in docs/manual/en: {missing}"


@pytest.mark.parametrize("entry", ENTRIES, ids=_id)
def test_spanish_answers_use_the_decimal_comma(entry) -> None:
    assert not re.search(r"\d\.\d", entry.es.answer)


@pytest.mark.parametrize("entry, lang", [t for t in TEXTS if t[0].kind != "design"], ids=_id)
def test_expected_mentions_match_the_answer(entry, lang) -> None:
    answer = entry.text(lang).answer
    for pattern in entry.expect.mentions:
        assert re.search(pattern, answer, re.IGNORECASE), pattern


@pytest.mark.parametrize("entry, lang", TEXTS, ids=_id)
def test_no_answer_claims_a_card(entry, lang) -> None:
    assert not claims_a_card(entry.text(lang).answer)


def test_the_fallback_claims_no_card() -> None:
    assert not claims_a_card(BANK.fallback.en)
    assert not claims_a_card(BANK.fallback.es)


DESIGNS = [e for e in ENTRIES if e.kind == "design"]


def test_seven_designs_four_valid() -> None:
    assert len(DESIGNS) == 7
    assert sum(e.expect.valid for e in DESIGNS) == 4


@pytest.mark.parametrize("entry", DESIGNS, ids=_id)
def test_design_proposals_validate_as_expected(entry) -> None:
    proposal = entry.proposal
    assert proposal is not None and proposal.family == entry.expect.family
    result = validate_parameters(
        proposal.family, get_family(proposal.family).defaults() | proposal.params
    )
    assert result.ok is entry.expect.valid
    assert result.rules == sorted(entry.expect.rules)
    for name, want in entry.expect.params.items():
        got = result.params[name]
        if isinstance(want, float):
            assert got == pytest.approx(want, abs=0.05), name
        else:
            assert got == want, name


def test_the_committed_markdown_is_up_to_date() -> None:
    """`docs/qa/qa_bank.md` is generated: run `python scripts/qa_bank_md.py` after editing."""
    import importlib.util
    import json

    from app.core.config import REPO_ROOT
    from app.core.content import QA_BANK

    spec = importlib.util.spec_from_file_location(
        "qa_bank_md", REPO_ROOT / "scripts" / "qa_bank_md.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    expected = module.render(json.loads(QA_BANK.read_text(encoding="utf-8")))
    committed = module.OUT.read_bytes().decode("utf-8").replace("\r\n", "\n")
    assert committed == expected, "run: python scripts/qa_bank_md.py"
