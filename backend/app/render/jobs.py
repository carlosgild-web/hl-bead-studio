"""Render jobs in SQLite (decision 0003): `queued -> running -> done | failed`.

`queue_render` is a side effect behind the confirmation gate (invariant 2): Phase 5's
`POST /actions/{id}/confirm` and the CLI call it; the assistant never does. `run_job` claims
a job atomically (so the in-process worker and a CLI run never render the same job twice),
runs Blender and records the outcome. Every step writes the audit log (invariant 9).

Renders live in `<DESIGNS_ROOT>/<SKU>/<Rev>/render/<SKU>_<Rev>_<finish>.png` with the
Blender log beside them. Unlike the design files, a render may be replaced: it is derived
from the design and the studio scene, and rendering again is how a scene change reaches it.
"""

import json
import os
import shutil
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import DateTime, Engine, Float, Integer, String, Text, select, update
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.config import Settings
from app.core.paths import confined, design_dir, design_file_names
from app.db import Base, get_engine, write_audit
from app.render.presets import RESOLUTION_PX, job_spec, resolve_finish
from app.render.runner import RenderFailed, blender_command, run_blender
from app.standards.families import get_family

QUEUED, RUNNING, DONE, FAILED = "queued", "running", "done", "failed"
FINAL_STATUSES = frozenset({DONE, FAILED})
INTERRUPTED = "Interrupted: the server stopped while the job was running; queue it again"


class RenderError(Exception):
    """A render that cannot be queued; the message says why."""


class RenderJob(Base):
    __tablename__ = "render_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    sku: Mapped[str] = mapped_column(String(16), index=True)
    rev: Mapped[str] = mapped_column(String(4))
    finish: Mapped[str] = mapped_column(String(32))
    samples: Mapped[int] = mapped_column(Integer)
    resolution: Mapped[int] = mapped_column(Integer)
    actor: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_s: Mapped[float | None] = mapped_column(Float)
    image: Mapped[str | None] = mapped_column(String(255))  # relative to DESIGNS_ROOT
    error: Mapped[str | None] = mapped_column(Text)

    def to_dict(self) -> dict[str, Any]:
        def iso(value: datetime | None) -> str | None:
            if value is None:
                return None
            return (value if value.tzinfo else value.replace(tzinfo=UTC)).isoformat()

        return {
            "id": self.id,
            "status": self.status,
            "sku": self.sku,
            "rev": self.rev,
            "finish": self.finish,
            "samples": self.samples,
            "resolution": self.resolution,
            "actor": self.actor,
            "created_at": iso(self.created_at),
            "started_at": iso(self.started_at),
            "finished_at": iso(self.finished_at),
            "duration_s": self.duration_s,
            "image": self.image,
            "error": self.error,
        }


@lru_cache
def _engine(data_dir: Path) -> Engine:
    """The app database, with the jobs table created even if the engine already existed."""
    engine = get_engine(data_dir)
    RenderJob.__table__.create(engine, checkfirst=True)
    return engine


def _now() -> datetime:
    return datetime.now(UTC)


def render_file_name(sku: str, rev: str, finish: str) -> str:
    return f"{sku}_{rev}_{finish}.png"


def read_design(settings: Settings, sku: str, rev: str) -> dict[str, Any]:
    """The `params.json` record of a generated revision (validates SKU and revision)."""
    folder = design_dir(settings.designs_root, sku, rev)
    record_path = folder / design_file_names(sku, rev)["params"]
    if not record_path.is_file():
        raise RenderError(f"{sku} revision {rev} has no generated files; generate it first")
    return json.loads(record_path.read_text(encoding="utf-8"))


def queue_render(
    settings: Settings,
    sku: str,
    rev: str,
    finish: str | None = None,
    *,
    actor: str,
    samples: int | None = None,
    resolution: int = RESOLUTION_PX,
) -> dict[str, Any]:
    """Queue one render of a generated revision in a color (beads) or finish (charms);
    the default is the design's own."""
    record = read_design(settings, sku, rev)
    kind = get_family(record["family"]).kind
    try:
        finish = resolve_finish(kind, record["params"], finish)
    except ValueError as error:
        raise RenderError(str(error)) from error
    samples = settings.render_samples if samples is None else samples
    if not 1 <= samples <= 4096:
        raise RenderError(f"samples must be 1-4096, got {samples}")
    if not 64 <= resolution <= 4096:
        raise RenderError(f"resolution must be 64-4096 px, got {resolution}")

    job = RenderJob(
        status=QUEUED,
        sku=sku,
        rev=rev,
        finish=finish,
        samples=samples,
        resolution=resolution,
        actor=actor,
        created_at=_now(),
    )
    with Session(_engine(settings.data_dir)) as session:
        session.add(job)
        session.commit()
        result = job.to_dict()
    write_audit(
        settings.data_dir,
        "render.queued",
        actor=actor,
        sku=sku,
        rev=rev,
        details={"job_id": result["id"], "finish": finish, "samples": samples},
    )
    return result


def get_job(settings: Settings, job_id: int) -> dict[str, Any] | None:
    with Session(_engine(settings.data_dir)) as session:
        job = session.get(RenderJob, job_id)
        return job.to_dict() if job else None


def list_jobs(
    settings: Settings, sku: str | None = None, rev: str | None = None, limit: int = 100
) -> list[dict[str, Any]]:
    """Newest first."""
    query = select(RenderJob).order_by(RenderJob.id.desc()).limit(limit)
    if sku is not None:
        query = query.where(RenderJob.sku == sku)
    if rev is not None:
        query = query.where(RenderJob.rev == rev)
    with Session(_engine(settings.data_dir)) as session:
        return [job.to_dict() for job in session.scalars(query)]


def _claim(settings: Settings, job_id: int) -> dict[str, Any] | None:
    """Move one job from queued to running; `None` if someone else got it first."""
    with Session(_engine(settings.data_dir)) as session:
        claimed = session.execute(
            update(RenderJob)
            .where(RenderJob.id == job_id, RenderJob.status == QUEUED)
            .values(status=RUNNING, started_at=_now())
        )
        session.commit()
        if claimed.rowcount != 1:
            return None
        return session.get(RenderJob, job_id).to_dict()


def _finish(settings: Settings, job_id: int, **values: Any) -> dict[str, Any]:
    with Session(_engine(settings.data_dir)) as session:
        job = session.get(RenderJob, job_id)
        for key, value in values.items():
            setattr(job, key, value)
        job.finished_at = _now()
        session.commit()
        return job.to_dict()


def _render(settings: Settings, job: dict[str, Any], command: list[str]) -> tuple[str, float]:
    """Render into a work folder, then move the image into place in one step."""
    sku, rev, finish = job["sku"], job["rev"], job["finish"]
    record = read_design(settings, sku, rev)
    kind = get_family(record["family"]).kind
    model = design_dir(settings.designs_root, sku, rev) / design_file_names(sku, rev)["glb"]
    if not model.is_file():
        raise RenderFailed(f"{model.name} is missing; generate the revision again")
    name = render_file_name(sku, rev, finish)
    render_folder = confined(settings.designs_root, sku, rev, "render")
    work = confined(settings.designs_root, sku, rev, "render", f".job-{job['id']}")
    work.mkdir(parents=True, exist_ok=True)
    try:
        spec = job_spec(
            kind,
            finish,
            model_path=str(model),
            output_path=str(work / name),
            samples=job["samples"],
            resolution=job["resolution"],
        )
        elapsed = run_blender(
            spec,
            job_path=work / "job.json",
            log_path=render_folder / name.replace(".png", ".log"),
            timeout_s=settings.render_timeout_s,
            command=command,
        )
        os.replace(work / name, render_folder / name)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return (render_folder / name).relative_to(settings.designs_root.resolve()).as_posix(), elapsed


def run_job(
    settings: Settings, job_id: int, *, command: list[str] | None = None
) -> dict[str, Any] | None:
    """Claim and render one queued job. Returns the finished job, or `None` if it was not
    queued (already taken, finished or unknown). Never raises for a failed render: the
    failure is recorded on the job and in the audit log."""
    job = _claim(settings, job_id)
    if job is None:
        return None
    try:
        image, elapsed = _render(settings, job, command or blender_command(settings))
    except Exception as error:  # every failure ends the job, whatever raised it
        message = str(error) if isinstance(error, RenderFailed | RenderError) else repr(error)
        finished = _finish(settings, job_id, status=FAILED, error=message)
        action, details = "render.failed", {"job_id": job_id, "error": message}
    else:
        finished = _finish(settings, job_id, status=DONE, image=image, duration_s=round(elapsed, 1))
        action, details = "render.done", {"job_id": job_id, "image": image}
    details["finish"] = job["finish"]
    write_audit(
        settings.data_dir,
        action,
        actor=job["actor"],
        sku=job["sku"],
        rev=job["rev"],
        details=details,
    )
    return finished


def next_queued(settings: Settings) -> int | None:
    """The oldest queued job's id."""
    query = select(RenderJob.id).where(RenderJob.status == QUEUED).order_by(RenderJob.id)
    with Session(_engine(settings.data_dir)) as session:
        return session.scalars(query.limit(1)).first()


def recover_interrupted(settings: Settings) -> int:
    """Fail the jobs left `running` by a stopped server (run once at start-up, before the
    worker). They are not retried: a job that crashed the server would crash it again."""
    with Session(_engine(settings.data_dir)) as session:
        stuck = list(session.scalars(select(RenderJob).where(RenderJob.status == RUNNING)))
        for job in stuck:
            job.status, job.error, job.finished_at = FAILED, INTERRUPTED, _now()
        session.commit()
        rows = [(job.id, job.actor, job.sku, job.rev, job.finish) for job in stuck]
    for job_id, actor, sku, rev, finish in rows:
        write_audit(
            settings.data_dir,
            "render.failed",
            actor=actor,
            sku=sku,
            rev=rev,
            details={"job_id": job_id, "error": INTERRUPTED, "finish": finish},
        )
    return len(rows)
