"""`demo-reset`: back to the seed catalog, deleting only the demo's own data (decision 0024)."""

from pathlib import Path

import pytest

from app.cli import main
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
