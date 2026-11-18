"""A test harness for the assistant: the real API, a scripted FakeClient, the in-memory SAP.

`env.chat(script, text)` sends one message through `POST /api/chat` and returns the parsed
server-sent events; `env.confirm(action_id)` is the designer's click.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from fastapi.testclient import TestClient

from app.agent.tools import PreviewCache
from app.api import deps
from app.core.config import Settings, get_settings
from app.db.store import Store
from app.llm.fake import FakeClient, Step
from app.main import app
from app.sap.memory import InMemorySap


def parse_sse(body: str) -> list[tuple[str, dict[str, Any]]]:
    events, kind = [], None
    for line in body.splitlines():
        if line.startswith("event: "):
            kind = line.removeprefix("event: ")
        elif line.startswith("data: "):
            events.append((kind, json.loads(line.removeprefix("data: "))))
    return events


class AgentEnv:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.sap = InMemorySap()
        self.store = Store(settings.data_dir)
        self.previews = PreviewCache()
        self.clients: list[FakeClient] = []
        self._next_script: Sequence[Step] | None = None
        self.notified = 0
        app.dependency_overrides[get_settings] = lambda: self.settings
        app.dependency_overrides[deps.get_store] = lambda: self.store
        app.dependency_overrides[deps.get_previews] = lambda: self.previews
        app.dependency_overrides[deps.get_sap_factory] = lambda: self.sap.client
        app.dependency_overrides[deps.get_llm_factory] = lambda: self._client
        app.dependency_overrides[deps.get_render_notify] = lambda: self._notify
        self.http = TestClient(app)  # no `with`: the lifespan render worker stays off

    def _client(self) -> FakeClient:
        client = FakeClient(self._next_script)
        self.clients.append(client)
        return client

    def _notify(self) -> None:
        self.notified += 1

    def close(self) -> None:
        app.dependency_overrides.clear()

    # --- conversation ------------------------------------------------------------------

    def chat(
        self,
        script: Sequence[Step] | None,
        text: str,
        conversation_id: str | None = None,
        language: str = "en",
        panel: dict[str, Any] | None = None,
    ) -> list[tuple[str, dict[str, Any]]]:
        self._next_script = script
        body: dict[str, Any] = {"message": text, "language": language}
        if conversation_id:
            body["conversation_id"] = conversation_id
        if panel:
            body["panel"] = panel
        response = self.http.post("/api/chat", json=body)
        assert response.status_code == 200, response.text
        events = parse_sse(response.text)
        if script is not None:
            assert self.clients[-1].remaining == 0, "the script was not used up"
        return events

    def confirm(self, action_id: str):
        return self.http.post(f"/api/actions/{action_id}/confirm")

    def cancel(self, action_id: str):
        return self.http.post(f"/api/actions/{action_id}/cancel")

    @property
    def last_client(self) -> FakeClient:
        return self.clients[-1]


def of_type(events, kind: str) -> list[dict[str, Any]]:
    return [data for event, data in events if event == kind]


def answer(events) -> str:
    [message] = of_type(events, "message")
    return message["content"]
