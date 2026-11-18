"""Shared FastAPI dependencies. Tests override the factories (`app.dependency_overrides`) to
use a scripted FakeClient and the in-memory SAP stand-in."""

from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, Request

from app.agent.tools import PreviewCache
from app.core.config import Settings, get_settings
from app.core.limits import RateLimiter, enforce_rate_limit, get_rate_limiter
from app.db.store import Store
from app.llm import LLMClient, make_client
from app.sap import SapClient
from app.standards.manual_search import ManualIndex, get_manual_index

SettingsDep = Annotated[Settings, Depends(get_settings)]


@lru_cache
def _store(data_dir: str) -> Store:
    return Store(Path(data_dir))


def get_store(settings: SettingsDep) -> Store:
    return _store(str(settings.data_dir))


_previews = PreviewCache()


def get_previews() -> PreviewCache:
    return _previews


def get_manual() -> ManualIndex:
    return get_manual_index()


def get_sap_factory(settings: SettingsDep) -> Callable[[], SapClient]:
    return lambda: SapClient.from_settings(settings)


def get_llm_factory(settings: SettingsDep) -> Callable[[], LLMClient]:
    return lambda: make_client(settings)


def get_render_notify(request: Request) -> Callable[[], None]:
    """Wakes the render worker after a render is queued (no-op without a worker)."""
    worker = getattr(request.app.state, "render_worker", None)
    return worker.notify if worker is not None else (lambda: None)


def rate_limit(group: str) -> Any:
    """A route dependency: at most RATE_LIMIT_PER_MINUTE requests per client and group."""

    def dependency(
        request: Request,
        settings: SettingsDep,
        limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    ) -> None:
        enforce_rate_limit(group, request, settings, limiter)

    return Depends(dependency)


StoreDep = Annotated[Store, Depends(get_store)]
PreviewsDep = Annotated[PreviewCache, Depends(get_previews)]
ManualDep = Annotated[ManualIndex, Depends(get_manual)]
SapFactoryDep = Annotated[Callable[[], SapClient], Depends(get_sap_factory)]
LLMFactoryDep = Annotated[Callable[[], LLMClient], Depends(get_llm_factory)]
RenderNotifyDep = Annotated[Callable[[], None], Depends(get_render_notify)]
