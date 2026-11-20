"""Online safety limits (PLAN Phase 7): a per-client rate limit and a daily token cap.

Both are off when their setting is 0, which is the local default for the token cap. The
rate limiter is in memory (one process, one worker: decision 0003), keyed by the client
address and a route group, with a sliding one-minute window. Behind a proxy, run uvicorn
with `--proxy-headers` so the client address is the visitor's, not the proxy's.
"""

from __future__ import annotations

import math
import time
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from threading import Lock

from fastapi import HTTPException, Request

from app.core.config import Settings
from app.db.store import Store
from app.llm import effective_provider

WINDOW_S = 60.0
RATE_LIMITED = "Too many requests from this address; wait {seconds} s and try again."
TOKEN_CAP_REACHED = (
    "The assistant's daily budget for this demo is used up; it resets at 00:00 UTC. The "
    "parameter panel, the checks and the confirmation cards still work."
)


class RateLimiter:
    """At most `limit` hits per key in any `window_s` seconds."""

    def __init__(self, window_s: float = WINDOW_S, clock: Callable[[], float] = time.monotonic):
        self.window_s = window_s
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = Lock()

    def hit(self, key: str, limit: int) -> float | None:
        """Record a hit. Returns None if allowed, else the seconds until the next one is."""
        if limit <= 0:
            return None
        now = self._clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - self.window_s:
                hits.popleft()
            if len(hits) >= limit:
                return hits[0] + self.window_s - now
            hits.append(now)
            if len(self._hits) > 10_000:  # forget idle clients
                for idle in [k for k, v in self._hits.items() if not v]:
                    del self._hits[idle]
            return None


_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    return _limiter


def client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(
    group: str, request: Request, settings: Settings, limiter: RateLimiter
) -> None:
    wait = limiter.hit(f"{group}:{client_key(request)}", settings.rate_limit_per_minute)
    if wait is not None:
        seconds = max(1, math.ceil(wait))
        raise HTTPException(
            429, RATE_LIMITED.format(seconds=seconds), headers={"Retry-After": str(seconds)}
        )


def start_of_day(now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def enforce_token_cap(settings: Settings, store: Store) -> None:
    """Refuse a chat turn once today's model tokens (all conversations) reach the cap. A
    turn that starts under the cap finishes, so the cap can be passed by one turn."""
    cap = settings.daily_token_cap
    if cap <= 0 or effective_provider(settings) == "fake":
        return
    if store.tokens_since(start_of_day()) >= cap:
        raise HTTPException(429, TOKEN_CAP_REACHED)
