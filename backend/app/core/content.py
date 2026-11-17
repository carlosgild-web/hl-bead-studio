"""Paths to the company content (schemas, templates, fonts, manual) and cached loaders.

The content lives in the repo, outside the Python package, because it is shared with the
manual, the frontend and Blender. Everything here is read-only.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import REPO_ROOT

CAD_DIR = REPO_ROOT / "cad"
TEMPLATES_DIR = CAD_DIR / "templates"
FONTS_DIR = CAD_DIR / "fonts"
SCHEMAS_DIR = REPO_ROOT / "backend" / "app" / "standards" / "schemas"
MANUAL_DIR = REPO_ROOT / "docs" / "manual"


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
