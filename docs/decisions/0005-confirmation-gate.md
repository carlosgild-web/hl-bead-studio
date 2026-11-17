# 0005: Confirmation gate for side effects

**Status:** accepted (2026-11-17)

## Context

Three actions change the world: reserving a SKU and SAP material, generating the design files
(STEP, STL, GLB, drawing PDF) and queuing a render. A language model can misread a request,
be steered by text inside a product name or engraving (prompt injection), or simply be wrong.
None of these actions should depend on what the model decides.

## Decision

- The agent's tools for these actions are **requests**: `request_reserve_sku`,
  `request_generate_design` and `request_render` only create a pending action (stored with its
  validated arguments) and return its id. They never call SAP, CadQuery, FreeCAD or Blender.
- The UI shows the pending action as a confirmation card. The side effect happens only in
  `POST /actions/{id}/confirm`, triggered by the designer's click. The endpoint re-validates
  the stored arguments with `standards/validators.py` before acting.
- An action is confirmed at most once; expired or cancelled actions cannot be confirmed.
- Every confirmed action writes to `audit_log` (invariant 9).

## Consequences

- No unconfirmed side effects, which the Phase 7 evaluation scores explicitly.
- The model can still propose and explain everything; the designer stays in control.
- One extra click per action, which is the point.
