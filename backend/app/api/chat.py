"""The assistant: `POST /api/chat` (one turn, as server-sent events), the conversation and the
trace of a run.

Events, in order: `conversation` {id}; then any of `thinking`, `tool_call`, `tool_result`,
`parameter_proposal`, `preview`, `pending_action`, `message`, `error`; finally `done`
{conversation_id, run_id, status}.
"""

import json
from collections.abc import Iterator
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from app.agent.loop import AgentEvent
from app.agent.service import AgentDeps, chat_turn, visible_conversation
from app.api.deps import (
    LLMFactoryDep,
    ManualDep,
    PreviewsDep,
    SapFactoryDep,
    SettingsDep,
    StoreDep,
)
from app.llm import LLMError

router = APIRouter(prefix="/api", tags=["assistant"])

MESSAGE_MAX = 2000
PANEL_MAX_PARAMS = 16


class Panel(BaseModel):
    """What the parameter panel shows when the designer sends the message (data)."""

    family: str = Field(default="", max_length=8)
    params: dict[str, Any] = Field(default_factory=dict, max_length=PANEL_MAX_PARAMS)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MESSAGE_MAX)
    conversation_id: str | None = Field(default=None, max_length=32)
    language: Literal["en", "es"] = "en"
    panel: Panel | None = None


def sse(event: AgentEvent) -> str:
    return f"event: {event.type}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"


def _panel(panel: Panel | None) -> dict[str, Any] | None:
    if panel is None or not (panel.family or panel.params):
        return None
    params = {
        str(k)[:40]: (v[:200] if isinstance(v, str) else v)
        for k, v in panel.params.items()
        if isinstance(v, str | int | float | bool)
    }
    return {"family": panel.family, "params": params}


@router.post("/chat")
def chat(
    body: ChatRequest,
    settings: SettingsDep,
    store: StoreDep,
    manual: ManualDep,
    previews: PreviewsDep,
    sap_factory: SapFactoryDep,
    llm_factory: LLMFactoryDep,
) -> StreamingResponse:
    if body.conversation_id and not store.conversation_exists(body.conversation_id):
        raise HTTPException(404, "Conversation not found")

    def stream() -> Iterator[str]:
        try:
            client = llm_factory()
        except LLMError as exc:
            yield sse(AgentEvent("error", {"message": str(exc)}))
            yield sse(AgentEvent("done", {"status": "error"}))
            return
        try:
            with sap_factory() as sap:
                deps = AgentDeps(
                    settings=settings,
                    store=store,
                    client=client,
                    sap=sap,
                    manual=manual,
                    previews=previews,
                )
                for event in chat_turn(
                    deps,
                    text=body.message,
                    conversation_id=body.conversation_id,
                    panel=_panel(body.panel),
                    language=body.language,
                ):
                    yield sse(event)
        finally:
            client.close()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, store: StoreDep) -> dict[str, Any]:
    conversation = visible_conversation(store, conversation_id)
    if conversation is None:
        raise HTTPException(404, "Conversation not found")
    return conversation


@router.get("/runs/{run_id}")
def get_run(run_id: int, store: StoreDep) -> dict[str, Any]:
    """The trace of one agent run (invariant 7)."""
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    return run


@router.get("/previews/{preview_id}.glb")
def get_preview(preview_id: str, previews: PreviewsDep) -> Response:
    """A GLB built by `preview_geometry` (in memory; gone after a restart)."""
    glb = previews.get(preview_id)
    if glb is None:
        raise HTTPException(404, "Preview not found (previews are kept in memory)")
    return Response(glb, media_type="model/gltf-binary", headers={"Cache-Control": "no-store"})
