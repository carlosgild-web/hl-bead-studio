# 0014: Confirmation cards opened from the parameter panel

**Status:** accepted (2026-11-18). Extends decision 0005 (confirmation gate) and decision 0013.

## Context

In Phase 6, only the assistant could open a confirmation card. That left the designer stuck
in three cases:

- The `fake` provider (demo mode) answers with a notice and never opens a card.
- The small local model sometimes says "please confirm" without opening the card
  (decision 0012).
- The online demo without an API key would show a panel and a 3D model, but no way to
  reserve, generate or render.

The designer asked for "Reserve SKU…", "Generate files…" and "Render…" buttons in the
parameter panel. The UI's look and feel will be tuned later.

## Decision

1. **`POST /api/actions` opens a card, and does nothing else.**
   - It calls the same functions as the assistant's tools: `request_reserve_sku`,
     `request_generate_design` and `request_render`. So the panel gets the same checks:
     - GEN-03 on the name;
     - the validators on the parameters;
     - the SKU must exist in SAP and match the family;
     - an existing revision is never overwritten;
     - an approved color or finish for the render.
   - A refusal answers 422 with the tool's message and violations, and no card is created.
   - The side effect still happens only in `POST /api/actions/{id}/confirm`, after the
     click (invariant 2). The model has no route to this endpoint, because its tools are
     the only thing it can call.
2. **One open card per kind per conversation.** If a pending card of the same kind exists,
   the endpoint returns it instead of opening a second one.
3. **The assistant is told.** Opening a card from the panel appends a `bead_studio_event`
   with outcome `opened_from_panel` to the conversation. The model's next turn knows a card
   exists, even though it never opened it. The panel creates the conversation if there is
   none yet.
4. **The panel's buttons** are at the bottom of the parameter panel:
   - **Reserve SKU…** asks for a name and a collection; the collections come from
     `GET /api/families/{code}`.
   - **Generate files…** takes the reserved SKU (or one you type), revision A, and the
     panel's parameters. It is disabled while a rule is broken.
   - **Render…** uses the generated revision and the color or finish chosen in the viewer.
     It is disabled until files exist.
   - The card appears in the chat, as the assistant's cards do.

## Consequences

- The whole flow works without any language model. A second Playwright test covers it:
  family → reserve (a GEN-03 refusal first) → generate → render.
- Two paths now open cards, but there is still one path that acts: the gate. The checks
  live in one place, the tool functions, so the panel and the assistant cannot drift
  apart.
- The e2e ports can be moved with `E2E_API_PORT` and `E2E_UI_PORT`.

## Addendum (2026-11-19): the product name field

Carlos asked for clearer guidance on the name in "Reserve SKU…":

- The family word (GEN-03) is a fixed suffix after the field, so the designer types only the
  evocative words. If they type the family word too, it is not doubled.
- While typing (300 ms after the last key), `POST /api/names/check` shows:
  - the full name as SAP will store it;
  - the GEN-03 result against the SAP catalog, in the UI language;
  - a mechanical fix to click (Title Case, at most three words, the family word once);
  - up to three similar names.
- The route is read only and rate limited (group `names`). Without SAP it still checks the
  pattern and says the catalog was not checked.
- The check only informs. Opening the card checks the name again on the server, and only
  Confirm reserves (invariant 2).
- The assistant's reserve card is unchanged: the assistant checks its name with the same rule.
