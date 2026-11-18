"""Render routes: status, the SSE status stream, the image, and no route that queues."""

import json
import threading
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api import renders as renders_api
from app.core.config import Settings, get_settings
from app.main import app
from app.render import queue_render, run_job


@pytest.fixture
def client(designed: Settings, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(renders_api, "POLL_S", 0.05)
    app.dependency_overrides[get_settings] = lambda: designed
    try:
        yield TestClient(app)  # no `with`: the lifespan worker stays off
    finally:
        app.dependency_overrides.clear()


def _events(body: str) -> list[dict]:
    return [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ")
    ]


def test_status_of_a_job(client: TestClient, designed: Settings) -> None:
    job = queue_render(designed, "CH-2034", "A", actor="tester")

    response = client.get(f"/api/renders/{job['id']}")

    assert response.status_code == 200
    assert response.json() == job
    assert client.get("/api/renders/999").status_code == 404


def test_renders_of_a_design(
    client: TestClient, designed: Settings, fake_blender: list[str]
) -> None:
    first = queue_render(designed, "CH-2034", "A", "rhodium", actor="tester")
    run_job(designed, first["id"], command=fake_blender)
    second = queue_render(designed, "CH-2034", "A", "gold_plate", actor="tester")
    queue_render(designed, "GB-1034", "A", actor="tester")

    jobs = client.get("/api/designs/CH-2034/A/renders").json()

    assert [(j["id"], j["status"]) for j in jobs] == [
        (second["id"], "queued"),
        (first["id"], "done"),
    ]
    assert client.get("/api/designs/CH-2034/B/renders").json() == []
    assert client.get("/api/designs/XX-1/A/renders").status_code == 422
    assert client.get("/api/designs/CH-2034/I/renders").status_code == 422


def test_image_only_when_done(
    client: TestClient, designed: Settings, fake_blender: list[str]
) -> None:
    job = queue_render(designed, "GB-1034", "A", actor="tester")
    assert client.get(f"/api/renders/{job['id']}/image").status_code == 409

    run_job(designed, job["id"], command=fake_blender)
    response = client.get(f"/api/renders/{job['id']}/image")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")


def test_events_of_a_finished_job_end_at_once(
    client: TestClient, designed: Settings, fake_blender: list[str]
) -> None:
    job = queue_render(designed, "CH-2034", "A", actor="tester")
    run_job(designed, job["id"], command=fake_blender)

    response = client.get(f"/api/renders/{job['id']}/events")

    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: status" in response.text
    assert [e["status"] for e in _events(response.text)] == ["done"]


def test_events_follow_a_job_until_it_is_done(
    client: TestClient, designed: Settings, fake_blender: list[str]
) -> None:
    job = queue_render(designed, "CH-2034", "A", actor="tester")
    timer = threading.Timer(0.3, run_job, (designed, job["id"]), {"command": fake_blender})
    timer.start()
    try:
        response = client.get(f"/api/renders/{job['id']}/events")
    finally:
        timer.join()

    statuses = [e["status"] for e in _events(response.text)]
    assert statuses[0] == "queued"
    assert statuses[-1] == "done"
    assert statuses == sorted(set(statuses), key=statuses.index)  # each change once


def test_events_of_an_unknown_job(client: TestClient) -> None:
    assert client.get("/api/renders/999/events").status_code == 404


def test_no_route_queues_a_render(client: TestClient) -> None:
    """Queuing is a side effect: only the confirmation gate may do it (invariant 2)."""
    for route in app.routes:
        methods = getattr(route, "methods", set())
        if "render" in getattr(route, "path", ""):
            assert methods <= {"GET", "HEAD"}, route.path


def test_the_app_starts_and_stops_the_render_worker(
    designed: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.main.get_settings", lambda: designed)

    with TestClient(app):
        worker = app.state.render_worker
        assert worker.alive
        assert worker.settings is designed
    assert not worker.alive
