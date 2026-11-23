"""`python -m app.cli demo-reset`: back to the clean demo (QA 2026-11-23, decision 0024).

Hand testing leaves reserved SKUs ("Test Flow Round"), generated revisions and renders
behind. The reset deletes, after asking:

- the app database `<DATA_DIR>/bead_studio.sqlite3`: conversations, cards, render jobs and
  the audit log (which describes the deleted designs, so it goes with them);
- everything under `DESIGNS_ROOT`: the generated files and their renders;
- the mock SAP database `<DATA_DIR>/sap_mock.db`, which the mock re-creates from
  `sap-mock/seed/materials.json` on its next start (the seed is the catalog).

The servers must be stopped first: on Windows an open SQLite file cannot be deleted, and the
reset then says so and changes nothing more. Only these paths are touched (invariant 4).
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import Settings
from app.db.base import DB_FILE

SAP_DB_FILE = "sap_mock.db"
_SQLITE_SIDECARS = ("", "-wal", "-shm", "-journal")


class ResetError(RuntimeError):
    pass


@dataclass
class ResetPlan:
    files: list[Path] = field(default_factory=list)
    folders: list[Path] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not self.files and not self.folders


def plan_reset(settings: Settings, sap_db: Path | None = None) -> ResetPlan:
    """What a reset would delete (only what exists)."""
    data_dir = settings.data_dir.resolve()
    designs = settings.designs_root.resolve()
    _check_designs_root(designs, data_dir)
    plan = ResetPlan()
    for database in (data_dir / DB_FILE, (sap_db or data_dir / SAP_DB_FILE).resolve()):
        plan.files += [p for s in _SQLITE_SIDECARS if (p := Path(f"{database}{s}")).is_file()]
    if designs.is_dir() and any(designs.iterdir()):
        plan.folders.append(designs)
    return plan


def run_reset(plan: ResetPlan) -> None:
    """Delete the plan's files, then its folders. A locked database stops the reset."""
    for path in plan.files:
        try:
            path.unlink()
        except PermissionError as exc:
            raise ResetError(
                f"{path.name} is in use: stop the servers (the start.cmd window, or "
                "docker compose down), then run demo-reset again."
            ) from exc
    for folder in plan.folders:
        for child in folder.iterdir():
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink()


def _check_designs_root(designs: Path, data_dir: Path) -> None:
    """Refuse a DESIGNS_ROOT that is not a designs folder (a typo must not empty a drive)."""
    if designs == data_dir or designs in data_dir.parents or designs == Path(designs.anchor):
        raise ResetError(f"DESIGNS_ROOT {designs} contains DATA_DIR; refusing to empty it.")
    if data_dir not in designs.parents and designs.name != "designs":
        raise ResetError(
            f"DESIGNS_ROOT {designs} is neither inside DATA_DIR nor a folder named 'designs'; "
            "refusing to empty it."
        )
