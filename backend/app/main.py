"""FastAPI entry point: `uvicorn app.main:app --reload --port 8000`."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api.actions import router as actions_router
from app.api.catalog import router as catalog_router
from app.api.chat import router as chat_router
from app.api.families import router as families_router
from app.api.renders import router as renders_router
from app.cleanup import CleanupThread
from app.core.config import get_settings
from app.render import RenderWorker, blender_available


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start the single render worker and the design cleanup (when enabled) with the app,
    and stop them on shutdown."""
    settings = get_settings()
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
        "llm_provider": settings.llm_provider,
        "renders": blender_available(settings),
    }
