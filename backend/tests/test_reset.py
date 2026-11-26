"""`demo-reset`: back to the seed catalog, deleting only the demo's own data (decision 0024)."""

from pathlib import Path

import pytest

from app.cli import main
from app.core.config import Settings
from app.reset import ResetError, plan_reset, run_reset
from tests.conftest import make_settings


@pytest.fixture
def used(tmp_path: Path):
    """A demo after a day of hand testing, next to a file the reset must leave alone."""
    settings = make_settings(tmp_path, designs_root=tmp_path / "data" / "designs")
    data = settings.data_dir
    (settings.designs_root / "GB-1040" / "A" / "render").mkdir(parents=True)
    (settings.designs_root / "GB-1040" / "A" / "GB-1040_A.step").write_text("step")
    (data / "bead_studio.sqlite3").write_bytes(b"app")
    (data / "bead_studio.sqlite3-wal").write_bytes(b"wal")
    (data / "sap_mock.db").write_bytes(b"sap")
    (data / "notes.txt").write_text("mine")
    return settings


def test_the_reset_deletes_the_databases_and_the_designs_only(used) -> None:
    plan = plan_reset(used)
    run_reset(plan)

    data = used.data_dir
    assert sorted(p.name for p in data.iterdir()) == ["designs", "notes.txt"]
    assert list(used.designs_root.iterdir()) == []


def test_a_clean_demo_has_nothing_to_delete(tmp_path) -> None:
    assert plan_reset(make_settings(tmp_path)).empty


def test_a_designs_root_that_holds_the_data_is_refused(tmp_path) -> None:
    with pytest.raises(ResetError):
        plan_reset(make_settings(tmp_path, designs_root=tmp_path))
    with pytest.raises(ResetError):
        plan_reset(make_settings(tmp_path, designs_root=tmp_path / "Documents"))


def test_the_cli_asks_unless_yes(used, monkeypatch, capsys) -> None:
    monkeypatch.setattr("app.cli.get_settings", lambda: used)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    assert main(["demo-reset"]) == 1  # no terminal and no --yes: nothing deleted
    assert (used.data_dir / "sap_mock.db").is_file()

    assert main(["demo-reset", "--yes"]) == 0
    assert not (used.data_dir / "sap_mock.db").exists()
    assert "seed/materials.json" in capsys.readouterr().out


def _fill(data: Path) -> None:
    (data / "designs" / "GB-1040" / "A").mkdir(parents=True)
    (data / "designs" / "GB-1040" / "A" / "GB-1040_A.step").write_text("step")
    (data / "bead_studio.sqlite3").write_bytes(b"app")
    (data / "sap_mock.db").write_bytes(b"sap")


def test_video_mode_resets_data_video_and_leaves_data_alone(tmp_path, monkeypatch) -> None:
    """`start.cmd video` sets DATA_DIR and DESIGNS_ROOT to data-video, then runs
    `demo-reset --yes` (decision 0026): every take starts on the seed, the user's data stays."""
    data, video = tmp_path / "data", tmp_path / "data-video"
    _fill(data)
    _fill(video)
    monkeypatch.setenv("DATA_DIR", str(video))
    monkeypatch.setenv("DESIGNS_ROOT", str(video / "designs"))
    settings = Settings(_env_file=None)
    monkeypatch.setattr("app.cli.get_settings", lambda: settings)

    assert main(["demo-reset", "--yes"]) == 0

    assert sorted(p.name for p in video.iterdir()) == ["designs"]
    assert list((video / "designs").iterdir()) == []
    left = sorted(p.name for p in data.iterdir())
    assert left == ["bead_studio.sqlite3", "designs", "sap_mock.db"]
    assert (data / "designs" / "GB-1040" / "A" / "GB-1040_A.step").read_text() == "step"


def test_the_first_video_start_has_nothing_to_reset(tmp_path, monkeypatch, capsys) -> None:
    video = tmp_path / "data-video"
    monkeypatch.setenv("DATA_DIR", str(video))
    monkeypatch.setenv("DESIGNS_ROOT", str(video / "designs"))
    settings = Settings(_env_file=None)
    monkeypatch.setattr("app.cli.get_settings", lambda: settings)

    assert main(["demo-reset", "--yes"]) == 0
    assert "already clean" in capsys.readouterr().out
