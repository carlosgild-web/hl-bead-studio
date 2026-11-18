"""The confirmation gate (invariant 2, decision 0005).

`POST /api/actions/{id}/confirm` is called by the designer's click on a confirmation card. It
is the only endpoint that reserves a SKU, writes design files or queues a render; the model
cannot reach it. Status codes: 200 done, 404 unknown, 409 already decided, 410 expired, 422 a
rule is broken, 409 the revision exists, 502 SAP failed, 500 an internal error. The body is
always the action with its result.

`POST /api/actions` opens a card from the parameter panel, without the assistant (decision
0014). It runs the same checks as the assistant's `request_*` tools and acts on nothing: the
card still waits for the click on Confirm.
"""

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError

from app.actions import ActionNotFound, ActionNotPending, cancel_action, confirm_action
from app.agent.prompts import event_message
from app.agent.tools import (
    GenerateArgs,
    RenderArgs,
    ReserveArgs,
    ToolContext,
    ToolResult,
    request_generate_design,
    request_render,
    request_reserve_sku,
)
from app.api.deps import (
    ManualDep,
    PreviewsDep,
    RenderNotifyDep,
    SapFactoryDep,
    SettingsDep,
    StoreDep,
    rate_limit,
)
from app.sap import SapError
from app.standards.families import UnknownFamilyError
from app.standards.identifiers import InvalidIdentifierError

router = APIRouter(prefix="/api/actions", tags=["actions"])

FAILURE_STATUS = {
    "validation": 422,
    "design": 422,
    "conflict": 409,
    "sap_unavailable": 502,
    "sap": 502,
    "render_unavailable": 503,
}


class OpenCard(BaseModel):
    """A card the designer opens from the panel. Free text is data, as in the chat."""

    kind: Literal["reserve_sku", "generate_design", "render"]
    conversation_id: str | None = Field(default=None, max_length=32)
    language: Literal["en", "es"] = "en"
    family: str = Field(default="", max_length=8)
    name: str = Field(default="", max_length=60)
    collection: str = Field(default="", max_length=30)
    sku: str = Field(default="", max_length=16)
    rev: str = Field(default="A", max_length=4)
    params: dict[str, Any] = Field(default_factory=dict, max_length=16)
    finish: str = Field(default="", max_length=30)


OPENERS = {
    "reserve_sku": (request_reserve_sku, ReserveArgs, ("family", "name", "collection")),
    "generate_design": (request_generate_design, GenerateArgs, ("sku", "rev", "family", "params")),
    "render": (request_render, RenderArgs, ("sku", "rev", "finish")),
}


def _refused(result: ToolResult) -> JSONResponse:
    error = result.content.get("error") or {}
    message = error.get("message") or "The card was not opened."
    return JSONResponse({"detail": message, "result": result.content}, status_code=422)


@router.post("", dependencies=[rate_limit("actions")])
def open_card(
    body: OpenCard,
    settings: SettingsDep,
    store: StoreDep,
    manual: ManualDep,
    previews: PreviewsDep,
    sap_factory: SapFactoryDep,
) -> JSONResponse:
    """Open a confirmation card from the panel. An open card of the same kind in the
    conversation is returned instead of a second one."""
    conversation_id = body.conversation_id
    if not conversation_id or not store.conversation_exists(conversation_id):
        conversation_id = store.create_conversation(body.language)
    for existing in store.list_actions(conversation_id):
        if existing.kind == body.kind and existing.status == "pending" and not existing.expired:
            return JSONResponse({"conversation_id": conversation_id, "action": existing.to_dict()})

    tool, args_model, fields = OPENERS[body.kind]
    try:
        args = args_model(**{f: getattr(body, f) for f in fields})
    except ValidationError as exc:
        raise HTTPException(422, exc.errors()[0]["msg"]) from exc
    try:
        with sap_factory() as sap:
            ctx = ToolContext(
                settings=settings,
                store=store,
                sap=sap,
                manual=manual,
                previews=previews,
                conversation_id=conversation_id,
                language=body.language,
            )
            result = tool(args, ctx)
    except (UnknownFamilyError, InvalidIdentifierError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except SapError as exc:
        raise HTTPException(502, f"SAP is not available: {exc}") from exc
    if not result.ok or result.event is None:
        return _refused(result)

    action = result.event["action"]
    # The assistant learns about the card in its next turn, like any other event.
    event = {"action_id": action["id"], "kind": body.kind, "outcome": "opened_from_panel"}
    event |= {"payload": action["payload"]}
    store.append_messages(
        conversation_id, [{"role": "event", "content": event_message(event), "event": event}]
    )
    return JSONResponse({"conversation_id": conversation_id, "action": action})


def _not_pending(exc: ActionNotPending) -> JSONResponse:
    status = 410 if exc.reason == "expired" else 409
    return JSONResponse({"detail": exc.reason, "action": exc.action.to_dict()}, status_code=status)


@router.get("/{action_id}")
def get_action(action_id: str, store: StoreDep) -> dict[str, Any]:
    action = store.get_action(action_id)
    if action is None:
        raise HTTPException(404, "Action not found")
    return action.to_dict()


@router.post("/{action_id}/confirm", dependencies=[rate_limit("actions")])
def confirm(
    action_id: str,
    settings: SettingsDep,
    store: StoreDep,
    sap_factory: SapFactoryDep,
    notify: RenderNotifyDep,
) -> JSONResponse:
    try:
        with sap_factory() as sap:
            outcome = confirm_action(
                action_id, settings=settings, store=store, sap=sap, on_render_queued=notify
            )
    except ActionNotFound as exc:
        raise HTTPException(404, "Action not found") from exc
    except ActionNotPending as exc:
        return _not_pending(exc)
    status = 200 if outcome.ok else FAILURE_STATUS.get(outcome.error_kind or "", 500)
    return JSONResponse(outcome.action.to_dict(), status_code=status)


@router.post("/{action_id}/cancel", dependencies=[rate_limit("actions")])
def cancel(action_id: str, store: StoreDep) -> JSONResponse:
    try:
        action = cancel_action(action_id, store=store)
    except ActionNotFound as exc:
        raise HTTPException(404, "Action not found") from exc
    except ActionNotPending as exc:
        return _not_pending(exc)
    return JSONResponse(action.to_dict())
