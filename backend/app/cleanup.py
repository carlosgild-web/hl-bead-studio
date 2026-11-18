"""Delete old generated designs on a public demo (PLAN Phase 7, online safety).

With `DESIGNS_RETENTION_HOURS` above 0, a revision folder under `DESIGNS_ROOT` whose newest
file is older than that is deleted, with its renders and the records of its finished render
jobs. A revision with a queued or running render is kept until the job ends. Every deletion
is written to the audit log. SAP is not touched: the reservation stays, as it would in a
real system. Off (0) by default, so a designer's local files are never removed.
"""

from __future__ import annotations

import logging
import shutil
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.core.config import Settings
from app.core.paths import confined
from app.db import write_audit
from app.render.jobs import FINAL_STATUSES, forget_jobs, list_jobs
from app.standards.identifiers import InvalidIdentifierError, validate_revision, validate_sku

log = logging.getLogger(__name__)

ACTOR = "cleanup"


def _newest_change(folder: Path) -> datetime:
    times = [p.stat().st_mtime for p in folder.rglob("*") if p.is_file()]
    return datetime.fromtimestamp(max(times, default=folder.stat().st_mtime), UTC)


def remove_old_designs(settings: Settings, now: datetime | None = None) -> list[str]:
    """Delete the revisions older than the retention. Returns `SKU/rev` of each one."""
    hours = settings.designs_retention_hours
    root = settings.designs_root
    if hours <= 0 or not root.is_dir():
        return []
    cutoff = (now or datetime.now(UTC)) - timedelta(hours=hours)
    removed = []
    for sku_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        for rev_dir in sorted(p for p in sku_dir.iterdir() if p.is_dir()):
            try:
                sku, rev = validate_sku(sku_dir.name), validate_revision(rev_dir.name)
            except InvalidIdentifierError:
                continue  # not a design folder: leave it alone
            age = _newest_change(rev_dir)
            if age >= cutoff:
                continue
            if any(j["status"] not in FINAL_STATUSES for j in list_jobs(settings, sku, rev)):
                continue  # a render is queued or running
            shutil.rmtree(confined(root, sku, rev))
            jobs = forget_jobs(settings, sku, rev)
            write_audit(
                settings.data_dir,
                "design.removed",
                actor=ACTOR,
                sku=sku,
                rev=rev,
                details={"last_change": age.isoformat(timespec="seconds"), "render_jobs": jobs},
            )
            removed.append(f"{sku}/{rev}")
        emptied = any(r.startswith(f"{sku_dir.name}/") for r in removed)
        if emptied and not any(sku_dir.iterdir()):
            sku_dir.rmdir()
    return removed


class CleanupThread:
    """Runs `remove_old_designs` at start-up and then every `interval_s` (when enabled)."""

    def __init__(self, settings: Settings, interval_s: float = 3600.0) -> None:
        self.settings = settings
        self.interval_s = interval_s
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self.settings.designs_retention_hours <= 0:
            return
        self._thread = threading.Thread(target=self._loop, name="design-cleanup", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                removed = remove_old_designs(self.settings)
                if removed:
                    log.info("removed %d old design revision(s)", len(removed))
            except Exception:  # keep running; the next pass tries again
                log.exception("design cleanup failed")
            self._stop.wait(self.interval_s)
