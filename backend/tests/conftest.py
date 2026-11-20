"""Shared fixtures: isolated settings and the external-tool markers."""

import shutil
import sys
from datetime import date
from pathlib import Path

import pytest

from app.core.config import Settings


def make_settings(tmp_path: Path, **overrides) -> Settings:
    """Settings that ignore the developer's `.env` and write under `tmp_path`.

    BLENDER_BIN names a file that exists (this Python), so the render cards and the gate's
    Blender check pass; no test runs it as Blender (they pass `command=` or override it).
    The rate limit is off: the limiter is shared by the whole test session."""
    values = {
        "data_dir": tmp_path / "data",
        "designs_root": tmp_path / "designs",
        "blender_bin": sys.executable,
        "rate_limit_per_minute": 0,
        "llm_fallback": "",  # no probe of a real Ollama; fallback tests set it
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.fixture(autouse=True)
def _fresh_llm_choice():
    """The daily-limit switch and the `auto` choice are per process; each test starts clean."""
    from app.llm.check import reset_auto
    from app.llm.fallback import reset_switch

    reset_switch()
    reset_auto()
    yield
    reset_switch()
    reset_auto()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


# Generated once per session and copied into each render test's designs folder.
RENDER_DESIGNS = (
    ("RND", "GB-1034", {"diameter_mm": 8.0, "hole_mm": 1.5, "color": "cobalt"}),
    (
        "CRS",
        "CH-2034",
        {
            "height_mm": 16.0,
            "crescent_width_mm": 5.0,
            "has_star": True,
            "star_diameter_mm": 5.0,
            "thickness_mm": 1.5,
            "loop_inner_mm": 2.0,
            "loop_wall_mm": 1.0,
            "finish": "gold_plate",
        },
    ),
)


@pytest.fixture(scope="session")
def designs_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    from app.designs import generate_design

    settings = make_settings(tmp_path_factory.mktemp("designs-template"))
    for family, sku, params in RENDER_DESIGNS:
        generate_design(
            family, params, sku=sku, rev="A", settings=settings, on_date=date(2026, 11, 17)
        )
    return settings.designs_root


@pytest.fixture
def designed(settings: Settings, designs_template: Path) -> Settings:
    """Settings whose designs folder holds GB-1034/A (round, cobalt) and CH-2034/A
    (crescent, gold plate)."""
    shutil.copytree(designs_template, settings.designs_root)
    return settings


@pytest.fixture
def fake_blender() -> list[str]:
    """Command that runs tests/fake_blender.py in place of Blender (FAKE_BLENDER_MODE)."""
    return [sys.executable, str(Path(__file__).with_name("fake_blender.py")), "--"]


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


def blender_bin() -> str | None:
    """The configured blender if it exists (BLENDER_BIN: a path or a name on PATH)."""
    configured = Settings().blender_bin
    if Path(configured).is_file():
        return configured
    return shutil.which(configured)


@pytest.fixture
def blender() -> str:
    command = blender_bin()
    if command is None:
        pytest.skip("blender not found (set BLENDER_BIN)")
    return command


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    missing = {
        "freecad": freecad_cmd() is None and "freecadcmd not found (set FREECAD_CMD)",
        "blender": blender_bin() is None and "blender not found (set BLENDER_BIN)",
    }
    for marker, reason in missing.items():
        if reason:
            for item in items:
                if marker in item.keywords:
                    item.add_marker(pytest.mark.skip(reason=reason))
