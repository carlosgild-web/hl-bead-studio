"""The confirmation gate (invariant 2, decision 0005).

`POST /api/actions/{id}/confirm` is called by the designer's click on a confirmation card. It
is the only endpoint that reserves a SKU, writes design files or queues a render; the model
cannot reach it. Status codes: 200 done, 404 unknown, 409 already decided, 410 expired, 422 a
rule is broken, 409 the revision exists, 502 SAP failed, 500 an internal error. The body is
always the action with its result.
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.actions import ActionNotFound, ActionNotPending, cancel_action, confirm_action
from app.api.deps import RenderNotifyDep, SapFactoryDep, SettingsDep, StoreDep

router = APIRouter(prefix="/api/actions", tags=["actions"])

FAILURE_STATUS = {
    "validation": 422,
    "design": 422,
    "conflict": 409,
    "sap_unavailable": 502,
    "sap": 502,
}


def _not_pending(exc: ActionNotPending) -> JSONResponse:
    status = 410 if exc.reason == "expired" else 409
    return JSONResponse({"detail": exc.reason, "action": exc.action.to_dict()}, status_code=status)


@router.get("/{action_id}")
def get_action(action_id: str, store: StoreDep) -> dict[str, Any]:
    action = store.get_action(action_id)
    if action is None:
        raise HTTPException(404, "Action not found")
    return action.to_dict()


@router.post("/{action_id}/confirm")
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


@router.post("/{action_id}/cancel")
def cancel(action_id: str, store: StoreDep) -> JSONResponse:
    try:
        action = cancel_action(action_id, store=store)
    except ActionNotFound as exc:
        raise HTTPException(404, "Action not found") from exc
    except ActionNotPending as exc:
        return _not_pending(exc)
    return JSONResponse(action.to_dict())
