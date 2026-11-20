"""FastAPI entry point: `uvicorn app.main:app --reload --port 8000`."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app import __version__
from app.api.actions import router as actions_router
from app.api.catalog import router as catalog_router
from app.api.chat import router as chat_router
from app.api.families import router as families_router
from app.api.renders import router as renders_router
from app.cleanup import CleanupThread
from app.core.config import get_settings
from app.core.paths import UnsafePathError, confined
from app.llm import effective_provider
from app.render import RenderWorker, blender_available


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start the single render worker and the design cleanup (when enabled) with the app,
    and stop them on shutdown."""
    settings = get_settings()
    if settings.llm_provider == "auto":
        from app.llm.check import resolve_auto

        resolve_auto(settings)  # once, before the first chat turn (decision 0019)
    worker = RenderWorker(settings)
    worker.start()
    app.state.render_worker = worker
    cleanup = CleanupThread(settings)
    cleanup.start()
    try:
        yield
    finally:
        cleanup.stop()
        worker.stop()


app = FastAPI(title="Bead Studio", version=__version__, lifespan=lifespan)
app.include_router(chat_router)
app.include_router(actions_router)
app.include_router(renders_router)
app.include_router(families_router)
app.include_router(catalog_router)


@app.get("/api/health")
def health() -> dict[str, str | bool]:
    """Liveness probe. Reports the version, the LLM provider and whether Blender is
    installed (renders run only where it is)."""
    settings = get_settings()
    return {
        "status": "ok",
        "version": __version__,
        "llm_provider": effective_provider(settings),
        "renders": blender_available(settings),
    }


def mount_frontend(target: FastAPI, dist: Path) -> bool:
    """Serve the built frontend, for a single process in Docker (decision 0018): a file of
    `dist` when the path names one, else `index.html` (the app has no router of its own,
    decision 0013). Call it after the API routers, so every `/api` route wins. In
    development Vite serves the frontend instead, and `dist` does not exist."""
    if not (dist / "index.html").is_file():
        return False

    @target.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        if path:
            try:
                file = confined(dist, path)
            except UnsafePathError as exc:
                raise HTTPException(404, "Not found") from exc
            if file.is_file():
                return FileResponse(file)
        return FileResponse(dist / "index.html", headers={"Cache-Control": "no-cache"})

    return True


mount_frontend(app, get_settings().frontend_dist)
