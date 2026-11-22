"""Paths to the company content (schemas, templates, fonts, manual, Q&A bank) and cached
loaders.

The content lives in the repo, outside the Python package, because it is shared with the
manual, the frontend and Blender. Everything here is read-only.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.core.config import REPO_ROOT

CAD_DIR = REPO_ROOT / "cad"
TEMPLATES_DIR = CAD_DIR / "templates"
FONTS_DIR = CAD_DIR / "fonts"
SCHEMAS_DIR = REPO_ROOT / "backend" / "app" / "standards" / "schemas"
MANUAL_DIR = REPO_ROOT / "docs" / "manual"
QA_BANK = REPO_ROOT / "docs" / "qa" / "qa_bank.json"


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache
def colors() -> dict[str, dict[str, Any]]:
    """Approved glass colors (rule GB-07) by id."""
    return {c["id"]: c for c in _load(TEMPLATES_DIR / "colors.json")["colors"]}


@lru_cache
def finishes() -> dict[str, dict[str, Any]]:
    """Approved charm finishes (rule CH-05) by id."""
    return {f["id"]: f for f in _load(TEMPLATES_DIR / "finishes.json")["finishes"]}


@lru_cache
def materials() -> dict[str, dict[str, Any]]:
    """Base materials (borosilicate, zinc alloy) by id, with their densities."""
    return {m["id"]: m for m in _load(TEMPLATES_DIR / "materials.json")["materials"]}


# --- the Q&A bank (decision 0022) ------------------------------------------------------------

QaKind = Literal["design", "knowledge", "howto", "guardrail"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class QaLanguage(_Strict):
    question: str
    variants: tuple[str, ...] = ()
    answer: str


class QaProposal(_Strict):
    family: str
    params: dict[str, Any]


class QaExpect(_Strict):
    """The fields of `app.eval.scenarios.Expect` the bank uses, plus `tools_any`."""

    family: str | None = None
    params: dict[str, Any] = {}
    valid: bool | None = None
    rules: tuple[str, ...] = ()
    mentions: tuple[str, ...] = ()
    cards: tuple[str, ...] = ()
    reserved: int = 0
    forbidden: tuple[str, ...] = ()
    tools_any: tuple[str, ...] = ()


class QaKeywords(_Strict):
    en: tuple[str, ...] = ()
    es: tuple[str, ...] = ()


class QaEntry(_Strict):
    id: str
    kind: QaKind
    category: str
    rules: tuple[str, ...] = ()
    manual: str | None = None
    search: str | None = None
    proposal: QaProposal | None = None
    keywords: QaKeywords
    en: QaLanguage
    es: QaLanguage
    expect: QaExpect

    def text(self, language: str) -> QaLanguage:
        return self.es if language == "es" else self.en


class QaFallback(_Strict):
    en: str
    es: str


class QaBank(_Strict):
    version: int
    manual_edition: str
    description: str
    kinds: dict[QaKind, str]
    fallback: QaFallback
    entries: tuple[QaEntry, ...]


@lru_cache
def qa_bank() -> QaBank:
    """The Q&A bank for demo mode and the `qa` eval suite; unknown keys are an error."""
    return QaBank.model_validate(_load(QA_BANK))
