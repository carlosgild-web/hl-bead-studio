"""Online safety: the rate limit, the daily token cap and the cleanup of old designs."""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime, timedelta

import pytest

from app.cleanup import remove_old_designs
from app.core.limits import TOKEN_CAP_REACHED, RateLimiter, get_rate_limiter, start_of_day
from app.db import read_audit
from app.llm.fake import say
from app.main import app
from app.render import list_jobs, queue_render
from tests.agent_env import AgentEnv


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_the_limiter_allows_the_limit_per_window():
    clock = Clock()
    limiter = RateLimiter(window_s=60, clock=clock)
    assert [limiter.hit("a", 2) for _ in range(2)] == [None, None]
    assert limiter.hit("a", 2) == pytest.approx(60)
    assert limiter.hit("b", 2) is None  # another client
    clock.now += 30
    assert limiter.hit("a", 2) == pytest.approx(30)
    clock.now += 30
    assert limiter.hit("a", 2) is None


def test_a_limit_of_zero_is_off():
    limiter = RateLimiter()
    assert all(limiter.hit("a", 0) is None for _ in range(1000))


@pytest.fixture
def env(settings):
    environment = AgentEnv(settings)
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    limiter = RateLimiter()
    yield environment
    environment.close()


def test_chat_over_the_limit_is_refused_with_retry_after(env):
    env.settings = env.settings.model_copy(update={"rate_limit_per_minute": 2})
    for _ in range(2):
        env.chat([say("hi")], "hello")
    response = env.http.post("/api/chat", json={"message": "hello"})
    assert response.status_code == 429
    assert 1 <= int(response.headers["retry-after"]) <= 60
    assert "Too many requests" in response.json()["detail"]
    assert len(env.clients) == 2  # the refused turn reached no model


def test_route_groups_have_their_own_budget(env):
    env.settings = env.settings.model_copy(update={"rate_limit_per_minute": 1})
    env.chat([say("hi")], "hello")
    body = {"family": "RND", "params": {"diameter_mm": 8.0, "hole_mm": 1.5, "color": "amber"}}
    assert env.http.post("/api/preview", json=body).status_code == 200
    assert env.http.post("/api/preview", json=body).status_code == 429
    assert env.http.post("/api/actions/" + "0" * 32 + "/cancel").status_code == 404


def _spend_tokens(env, tokens: int) -> None:
    conversation = env.store.create_conversation()
    run = env.store.start_run(conversation, "anthropic", "test")
    env.store.finish_run(run, status="answered", model_calls=1, tokens=tokens, trace={})


def test_chat_stops_at_the_daily_token_cap(env):
    env.settings = env.settings.model_copy(
        update={"daily_token_cap": 1000, "llm_provider": "anthropic"}
    )
    _spend_tokens(env, 999)
    env.chat([say("still under the cap")], "hello")
    _spend_tokens(env, 1)

    response = env.http.post("/api/chat", json={"message": "hello"})

    assert response.status_code == 429
    assert response.json()["detail"] == TOKEN_CAP_REACHED
    assert len(env.clients) == 1


def test_the_token_cap_does_not_apply_to_the_fake_client(env):
    env.settings = env.settings.model_copy(update={"daily_token_cap": 1})
    _spend_tokens(env, 10)
    env.chat([say("demo mode")], "hello")


def test_the_day_starts_at_midnight_utc():
    now = datetime(2026, 11, 18, 23, 59, tzinfo=UTC)
    assert start_of_day(now) == datetime(2026, 11, 18, tzinfo=UTC)


# --- cleanup ----------------------------------------------------------------------------


def _age(folder, hours: float) -> None:
    then = time.time() - hours * 3600
    for path in folder.rglob("*"):
        os.utime(path, (then, then))


def test_old_designs_are_removed_and_audited(designed):
    settings = designed.model_copy(update={"designs_retention_hours": 24})
    _age(settings.designs_root / "GB-1034", 25)
    (settings.designs_root / "notes").mkdir()  # not a design folder: kept

    assert remove_old_designs(settings) == ["GB-1034/A"]

    assert not (settings.designs_root / "GB-1034").exists()
    assert (settings.designs_root / "CH-2034" / "A").is_dir()
    assert (settings.designs_root / "notes").is_dir()
    [entry] = read_audit(settings.data_dir)
    assert (entry["action"], entry["actor"], entry["sku"]) == (
        "design.removed",
        "cleanup",
        "GB-1034",
    )


def test_a_design_with_a_queued_render_is_kept(designed):
    settings = designed.model_copy(update={"designs_retention_hours": 1})
    queue_render(settings, "CH-2034", "A", actor="test")
    _age(settings.designs_root, 2)

    assert remove_old_designs(settings) == ["GB-1034/A"]
    assert (settings.designs_root / "CH-2034" / "A").is_dir()
    assert len(list_jobs(settings, "CH-2034")) == 1


def test_cleanup_is_off_by_default(designed):
    _age(designed.designs_root, 24 * 365)
    assert remove_old_designs(designed) == []
    assert remove_old_designs(designed, now=datetime.now(UTC) + timedelta(days=999)) == []
