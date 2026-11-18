"""Run one scenario through the real agent, tools and confirmation gate.

Everything is real except the model (the client the caller gives) and SAP, which is the
in-memory stand-in (`app.sap.memory`), so a run needs no sap-mock service and can take SAP
down on cue. Each scenario gets its own data folder and designs folder, so a run never
touches `data/`. The render worker is not started: a confirmed render stays queued, which
is the side effect the scorer counts. Without Blender, BLENDER_BIN points at a missing file.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from app.actions import ActionNotFound, ActionNotPending, cancel_action, confirm_action
from app.agent.service import AgentDeps, chat_turn
from app.agent.tools import PreviewCache
from app.core.config import Settings
from app.db.base import get_engine
from app.db.store import PENDING, Store
from app.designs import generate_design
from app.eval.scenarios import Click, SapDown, Scenario, Turn
from app.llm.base import LLMClient
from app.llm.fake import FakeClient
from app.render import list_jobs
from app.sap.memory import InMemorySap
from app.standards.families import get_family
from app.standards.manual_search import get_manual_index

ClientFactory = Callable[[Turn], LLMClient]


@dataclass
class TurnRecord:
    text: str
    answer: str = ""
    status: str = "error"
    error: str | None = None
    run_id: int | None = None
    trace: dict[str, Any] = field(default_factory=dict)
    cards: list[dict[str, Any]] = field(default_factory=list)  # pending_action events
    unused_script: int = 0  # FakeClient turns left over (the ideal script went wrong)
    seconds: float = 0.0


@dataclass
class ClickRecord:
    kind: str
    decision: str
    found: bool
    ok: bool = False
    error_kind: str | None = None


@dataclass
class ScenarioRun:
    """What happened: the turns, the clicks, the actions and the side effects counted."""

    scenario: Scenario
    provider: str = ""
    model: str = ""
    turns: list[TurnRecord] = field(default_factory=list)
    clicks: list[ClickRecord] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)
    reserved: int = 0
    reservation_bodies: list[str] = field(default_factory=list)
    designs: int = 0
    renders: int = 0
    seconds: float = 0.0

    @property
    def answers(self) -> list[str]:
        return [t.answer for t in self.turns]

    @property
    def tool_steps(self) -> list[dict[str, Any]]:
        return [s for t in self.turns for s in t.trace.get("steps", []) if s["type"] == "tool_call"]

    @property
    def checks(self) -> list[str]:
        return [
            s["check"] for t in self.turns for s in t.trace.get("steps", []) if s["type"] == "check"
        ]

    @property
    def model_calls(self) -> int:
        return sum(t.trace.get("model_calls", 0) for t in self.turns)

    @property
    def tokens(self) -> int:
        return sum(t.trace.get("tokens", 0) for t in self.turns)


def fake_clients(turn: Turn) -> LLMClient:
    """The ideal model of `agent-eval --fake`: the turn's script."""
    return FakeClient(turn.fake)


def _settings_for(scenario: Scenario, base: Settings, workdir: Path) -> Settings:
    blender = sys.executable if scenario.blender else str(workdir / "no-blender" / "blender")
    # `sys.executable` is a stand-in that exists: the worker never runs, nothing executes it.
    return base.model_copy(
        update={
            "data_dir": workdir / "data",
            "designs_root": workdir / "designs",
            "blender_bin": blender,
        }
    )


def _design_records(settings: Settings) -> set[Path]:
    root = settings.designs_root
    return set(root.glob("*/*/params.json")) if root.exists() else set()


def _prepare(scenario: Scenario, settings: Settings, sap: InMemorySap) -> None:
    with sap.client() as client:
        for p in scenario.prepared:
            family = get_family(p.family)
            material = client.reserve(
                family.kind, p.name, "EVAL", family=family.code, collection=p.collection
            )
            if p.generate:
                generate_design(
                    family.code,
                    family.defaults() | p.params,
                    sku=material.sku,
                    rev="A",
                    settings=settings,
                    name=p.name,
                    sap_material=material.material,
                    actor="eval",
                    on_date=date(2026, 11, 18),
                )


def run_scenario(
    scenario: Scenario, clients: ClientFactory, base: Settings, workdir: Path
) -> ScenarioRun:
    started = time.perf_counter()
    settings = _settings_for(scenario, base, workdir)
    sap = InMemorySap()
    store = Store(settings.data_dir)
    previews = PreviewCache()
    manual = get_manual_index()
    _prepare(scenario, settings, sap)
    reservations_before = len(sap.reservations)
    designs_before = _design_records(settings)

    run = ScenarioRun(scenario)
    conversation_id: str | None = None
    for step in scenario.steps:
        if isinstance(step, SapDown):
            sap.down = step.down
        elif isinstance(step, Turn):
            conversation_id = _turn(
                step,
                scenario,
                run,
                clients,
                settings,
                store,
                sap,
                previews,
                manual,
                conversation_id,
            )
        elif isinstance(step, Click):
            run.clicks.append(_click(step, settings, store, sap, conversation_id))

    if conversation_id:
        run.actions = [a.to_dict() for a in store.list_actions(conversation_id)]
    new_requests = sap.reservations[reservations_before:]
    run.reserved = len(new_requests)
    run.reservation_bodies = [r.content.decode("utf-8", "replace") for r in new_requests]
    run.designs = len(_design_records(settings) - designs_before)
    run.renders = len(list_jobs(settings))
    run.seconds = round(time.perf_counter() - started, 1)
    get_engine(settings.data_dir).dispose()  # close the SQLite file so the folder can go
    return run


def _turn(
    turn: Turn,
    scenario: Scenario,
    run: ScenarioRun,
    clients: ClientFactory,
    settings: Settings,
    store: Store,
    sap: InMemorySap,
    previews: PreviewCache,
    manual: Any,
    conversation_id: str | None,
) -> str | None:
    record = TurnRecord(turn.text)
    client = clients(turn)
    run.provider, run.model = client.provider, client.model
    started = time.perf_counter()
    try:
        with sap.client() as sap_client:
            deps = AgentDeps(
                settings=settings,
                store=store,
                client=client,
                sap=sap_client,
                manual=manual,
                previews=previews,
            )
            for event in chat_turn(
                deps,
                text=turn.text,
                conversation_id=conversation_id,
                panel=turn.panel,
                language=scenario.language,
            ):
                if event.type == "conversation":
                    conversation_id = event.data["id"]
                elif event.type == "message":
                    record.answer = event.data["content"]
                elif event.type == "pending_action":
                    record.cards.append(event.data["action"])
                elif event.type == "error":
                    record.error = event.data["message"]
                elif event.type == "done":
                    record.status = event.data["status"]
                    record.run_id = event.data["run_id"]
    finally:
        client.close()
    record.seconds = round(time.perf_counter() - started, 1)
    if isinstance(client, FakeClient):
        record.unused_script = client.remaining
    if record.run_id is not None:
        stored = store.get_run(record.run_id)
        record.trace = stored["trace"] if stored else {}
    run.turns.append(record)
    return conversation_id


def _click(
    click: Click, settings: Settings, store: Store, sap: InMemorySap, conversation_id: str | None
) -> ClickRecord:
    pending = [
        a
        for a in (store.list_actions(conversation_id) if conversation_id else [])
        if a.kind == click.kind and a.status == PENDING and not a.expired
    ]
    if not pending:
        return ClickRecord(click.kind, click.decision, found=False)
    action_id = pending[-1].id
    try:
        if click.decision == "cancel":
            cancel_action(action_id, store=store)
            return ClickRecord(click.kind, click.decision, found=True, ok=True)
        with sap.client() as sap_client:
            outcome = confirm_action(action_id, settings=settings, store=store, sap=sap_client)
    except (ActionNotFound, ActionNotPending) as exc:
        return ClickRecord(click.kind, click.decision, found=True, error_kind=str(exc))
    return ClickRecord(
        click.kind, click.decision, found=True, ok=outcome.ok, error_kind=outcome.error_kind
    )
