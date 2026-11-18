"""Render job routes: status, a live status stream (SSE) and the image.

All read-only. Queuing a render is a side effect, so it has no route here: it happens only
in `POST /actions/{id}/confirm` after the designer's click (invariant 2, Phase 5).
"""

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from app.core.config import Settings, get_settings
from app.core.paths import UnsafePathError, confined
from app.render import FINAL_STATUSES, get_job, list_jobs
from app.standards.identifiers import InvalidIdentifierError, validate_revision, validate_sku

router = APIRouter(prefix="/api", tags=["renders"])

SettingsDep = Annotated[Settings, Depends(get_settings)]

POLL_S = 0.5  # how often the stream looks at the job
KEEPALIVE_S = 15.0  # comment line so proxies keep an idle stream open
STREAM_LIMIT_S = 3600.0  # a browser EventSource reconnects after this


def _job_or_404(settings: Settings, job_id: int) -> dict[str, Any]:
    job = get_job(settings, job_id)
    if job is None:
        raise HTTPException(404, f"render job {job_id} not found")
    return job


@router.get("/renders/{job_id}")
def render_status(job_id: int, settings: SettingsDep) -> dict[str, Any]:
    return _job_or_404(settings, job_id)


@router.get("/renders/{job_id}/events")
async def render_events(job_id: int, settings: SettingsDep) -> StreamingResponse:
    """Server-sent events: a `status` event with the job each time it changes, ending after
    `done` or `failed`."""
    _job_or_404(settings, job_id)

    async def stream() -> AsyncIterator[str]:
        last: dict[str, Any] | None = None
        started = last_sent = time.monotonic()
        while time.monotonic() - started < STREAM_LIMIT_S:
            job = await asyncio.to_thread(get_job, settings, job_id)
            if job != last:
                yield f"event: status\ndata: {json.dumps(job)}\n\n"
                last, last_sent = job, time.monotonic()
                if job is None or job["status"] in FINAL_STATUSES:
                    return
            elif time.monotonic() - last_sent > KEEPALIVE_S:
                yield ": keep-alive\n\n"
                last_sent = time.monotonic()
            await asyncio.sleep(POLL_S)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/renders/{job_id}/image")
def render_image(job_id: int, settings: SettingsDep) -> FileResponse:
    job = _job_or_404(settings, job_id)
    if job["status"] != "done" or not job["image"]:
        raise HTTPException(409, f"render job {job_id} is {job['status']}, no image yet")
    try:
        path = confined(settings.designs_root, *job["image"].split("/"))
    except UnsafePathError as error:
        raise HTTPException(404, "image not found") from error
    if not path.is_file():
        raise HTTPException(404, "image not found (the design folder changed)")
    return FileResponse(path, media_type="image/png")


@router.get("/designs/{sku}/{rev}/renders")
def design_renders(sku: str, rev: str, settings: SettingsDep) -> list[dict[str, Any]]:
    """Render jobs of one revision, newest first."""
    try:
        validate_sku(sku)
        validate_revision(rev)
    except InvalidIdentifierError as error:
        raise HTTPException(422, str(error)) from error
    return list_jobs(settings, sku=sku, rev=rev)
