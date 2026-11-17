"""Shared fixtures: isolated settings and the external-tool markers."""

import shutil
from pathlib import Path

import pytest

from app.core.config import Settings


def make_settings(tmp_path: Path, **overrides) -> Settings:
    """Settings that ignore the developer's `.env` and write under `tmp_path`."""
    values = {"data_dir": tmp_path / "data", "designs_root": tmp_path / "designs"}
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


def freecad_cmd() -> str | None:
    """The configured freecadcmd if it exists (FREECAD_CMD: a path or a name on PATH)."""
    configured = Settings().freecad_cmd
    if Path(configured).is_file():
        return configured
    return shutil.which(configured)


@pytest.fixture
def freecad() -> str:
    command = freecad_cmd()
    if command is None:
        pytest.skip("freecadcmd not found (set FREECAD_CMD)")
    return command


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if freecad_cmd() is None:
        skip = pytest.mark.skip(reason="freecadcmd not found (set FREECAD_CMD)")
        for item in items:
            if "freecad" in item.keywords:
                item.add_marker(skip)
