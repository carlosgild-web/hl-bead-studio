"""FastAPI entry point: `uvicorn app.main:app --reload --port 8000`."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api.renders import router as renders_router
from app.core.config import get_settings
from app.render import RenderWorker


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start the single render worker with the app and stop it on shutdown."""
    worker = RenderWorker(get_settings())
    worker.start()
    app.state.render_worker = worker
    try:
        yield
    finally:
        worker.stop()


app = FastAPI(title="Bead Studio", version=__version__, lifespan=lifespan)
app.include_router(renders_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    """Liveness probe. Reports the version and which LLM provider is configured."""
    return {
        "status": "ok",
        "version": __version__,
        "llm_provider": get_settings().llm_provider,
    }
