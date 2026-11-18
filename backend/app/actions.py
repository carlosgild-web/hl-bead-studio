"""Confirm or cancel a pending action: the only place where side effects happen (invariant 2,
decision 0005). Called by `POST /api/actions/{id}/confirm` after the designer's click.

Before anything happens the stored arguments are checked again (validators, GEN-03 against a
fresh SAP catalog, the SAP record of the SKU), so a card cannot skip a rule or act on stale
data. An action is claimed atomically, so it runs at most once; expired or decided actions
cannot be confirmed. The outcome is stored on the action, written to `audit_log`
(invariant 9) and added to the conversation as a Bead Studio event, so the assistant reports
what actually happened.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.agent.prompts import event_message
from app.core.config import Settings
from app.db import write_audit
from app.db.store import CANCELLED, CONFIRMED, EXECUTING, FAILED, ActionRecord, Store
from app.designs import DesignError, InvalidDesignError, RevisionExistsError, generate_design
from app.render import RenderError, queue_render
from app.sap import SapClient, SapError
from app.standards.families import get_family
from app.standards.naming import CatalogEntry, validate_product_name

logger = logging.getLogger(__name__)

ACTOR = "designer"  # no sign-in in v1; the click comes from the designer at the UI
SAP_CREATED_BY = "BEADSTUDIO"


class ActionNotFound(LookupError):
    pass


class ActionNotPending(RuntimeError):
    """Already decided (confirmed, failed, cancelled, executing) or expired."""

    def __init__(self, action: ActionRecord, reason: str) -> None:
        super().__init__(reason)
        self.action = action
        self.reason = reason  # "expired" | "already_<status>"


@dataclass(frozen=True)
class ActionOutcome:
    action: ActionRecord
    ok: bool
    error_kind: str | None = None  # validation | sap_unavailable | sap | conflict | design


def _not_pending(store: Store, action_id: str) -> ActionNotPending:
    action = store.get_action(action_id)
    if action is None:
        raise ActionNotFound(action_id)
    reason = "expired" if action.expired else f"already_{action.status}"
    return ActionNotPending(action, reason)


def confirm_action(
    action_id: str,
    *,
    settings: Settings,
    store: Store,
    sap: SapClient,
    on_render_queued: Callable[[], None] | None = None,
) -> ActionOutcome:
    if store.get_action(action_id) is None:
        raise ActionNotFound(action_id)
    if not store.claim_action(action_id, to=EXECUTING):
        raise _not_pending(store, action_id)
    action = store.get_action(action_id)
    assert action is not None

    try:
        if action.kind == "reserve_sku":
            result = _reserve(action, settings, sap)
        elif action.kind == "generate_design":
            result = _generate(action, settings, sap)
        elif action.kind == "render":
            result = _render(action, settings)
            if result["ok"] and on_render_queued:
                on_render_queued()
        else:
            result = _failure("unknown", f"Unknown action kind {action.kind}")
    except Exception as exc:  # never leave an action stuck in "executing"
        logger.exception("action %s failed", action_id)
        result = _failure("internal", f"{exc.__class__.__name__}: {exc}")
    return _finish(store, action, result)


def cancel_action(action_id: str, *, store: Store) -> ActionRecord:
    if store.get_action(action_id) is None:
        raise ActionNotFound(action_id)
    if not store.claim_action(action_id, to=CANCELLED):
        raise _not_pending(store, action_id)
    action = store.get_action(action_id)
    assert action is not None
    _add_event(store, action, {"ok": False, "cancelled": True}, "cancelled")
    return action


# --- the three side effects ----------------------------------------------------------


def _reserve(action: ActionRecord, settings: Settings, sap: SapClient) -> dict[str, Any]:
    p = action.payload
    family = get_family(p["family"])
    try:
        catalog = [CatalogEntry(m.sku, m.description, m.status) for m in sap.list_materials()]
        violations = validate_product_name(p["name"], family, catalog)
        if violations:
            return _failure(
                "validation",
                "The name breaks GEN-03 now; nothing was reserved.",
                violations=[{"rule": v.rule, "message": v.message} for v in violations],
            )
        material = sap.reserve(
            family.kind,
            p["name"],
            SAP_CREATED_BY,
            family=family.code,
            collection=p.get("collection"),
        )
    except SapError as exc:
        return _sap_failure(exc, "nothing was reserved")
    write_audit(
        settings.data_dir,
        "sku.reserved",
        actor=ACTOR,
        sku=material.sku,
        rev=material.revision or "A",
        details={
            "action_id": action.id,
            "name": material.description,
            "family": family.code,
            "collection": material.collection or None,
            "sap_material": material.material,
        },
    )
    return {
        "ok": True,
        "sku": material.sku,
        "sap_material": material.material,
        "name": material.description,
        "family": family.code,
        "collection": material.collection or None,
        "status": material.status,
        "revision": material.revision or "A",
    }


def _generate(action: ActionRecord, settings: Settings, sap: SapClient) -> dict[str, Any]:
    p = action.payload
    try:
        material = sap.get_material(p["sku"])
    except SapError as exc:
        return _sap_failure(exc, "no files were written")
    if material.status == "DISCONTINUED":
        return _failure("validation", f"{p['sku']} is discontinued; no files were written.")
    try:
        design = generate_design(
            p["family"],
            p["params"],
            sku=p["sku"],
            rev=p["rev"],
            settings=settings,
            name=material.description,
            sap_material=material.material,
            actor=ACTOR,
        )
    except InvalidDesignError as exc:
        return _failure(
            "validation",
            str(exc),
            violations=[{"rule": v.rule, "message": v.message} for v in exc.result.violations],
        )
    except RevisionExistsError as exc:
        return _failure("conflict", f"{exc}. Nothing was overwritten.")
    except (DesignError, ValueError) as exc:
        return _failure("design", f"{exc}. No files were written.")
    return {
        "ok": True,
        "sku": design.sku,
        "rev": design.rev,
        "family": design.family,
        "name": material.description,
        "sap_material": material.material,
        "files": sorted(path.name for path in design.files.values()),
        "measurements": design.measurements,
        "drawing_scale": design.drawing_scale,
    }


def _render(action: ActionRecord, settings: Settings) -> dict[str, Any]:
    p = action.payload
    try:
        job = queue_render(settings, p["sku"], p["rev"], p["finish"], actor=ACTOR)
    except RenderError as exc:
        return _failure("validation", f"{exc}. Nothing was queued.")
    return {
        "ok": True,
        "sku": p["sku"],
        "rev": p["rev"],
        "finish": job["finish"],
        "job_id": job["id"],
        "status": job["status"],
    }


# --- outcome -------------------------------------------------------------------------


def _failure(kind: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "error_kind": kind, "message": message, **extra}


def _sap_failure(exc: SapError, nothing: str) -> dict[str, Any]:
    if exc.unavailable:
        return _failure(
            "sap_unavailable", f"SAP is not available ({exc.message}); {nothing}. Try again later."
        )
    return _failure("sap", f"SAP refused: {exc.code} {exc.message}; {nothing}.")


def _add_event(store: Store, action: ActionRecord, result: dict[str, Any], outcome: str) -> None:
    event = {"action_id": action.id, "kind": action.kind, "outcome": outcome, **result}
    store.append_messages(
        action.conversation_id,
        [{"role": "event", "content": event_message(event), "event": event}],
    )


def _finish(store: Store, action: ActionRecord, result: dict[str, Any]) -> ActionOutcome:
    status = CONFIRMED if result["ok"] else FAILED
    store.finish_action(action.id, status=status, result=result)
    _add_event(store, action, result, "done" if result["ok"] else "failed")
    final = store.get_action(action.id)
    assert final is not None
    return ActionOutcome(final, ok=result["ok"], error_kind=result.get("error_kind"))
