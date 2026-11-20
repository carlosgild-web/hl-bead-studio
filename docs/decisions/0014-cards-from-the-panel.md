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

## Addendum (2026-11-19): next-step chip, workflow stepper, out-of-date files

- **"Next step" chip.** The chip opens the next card directly, through `POST /api/actions`,
  the same path as the panel (`useOpenCard`). It no longer sends a chat message, so it works
  with any LLM provider, including `fake`. The chat scrolls only its own list, not the page.
- **Workflow stepper.** "Open a card yourself" becomes "Workflow", a vertical stepper whose
  states (current, done ✓, blocked) come from what the studio has (`workflowSteps` in
  `state.ts`), not from clicks.
  - Generate is blocked until a SKU is reserved, but "Use an existing SKU…" still opens its
    form. Render is blocked until files exist.
  - The submit button reads "Review & confirm". It is disabled while the product name is
    checked or breaks GEN-03, and the name check keeps a fixed height so the button does
    not move.
- **Out-of-date files.** The design record now has `next_rev`, the revision after the
  highest one with files. `paramsDiff` compares the panel with the generated revision's
  `params.json`: numbers to 0.001, key order ignored, labels from the family. Color and
  finish count as changes, because the title block prints them.
  - When the panel differs, a notice above the drawing, a marker on the Drawing tab, the
    Renders tab and the stepper show the changes.
  - The notice offers "Generate Rev B" (opens the card; existing revisions are never
    overwritten) and "Revert to Rev A parameters".
  - Render stays possible, with a note that it renders the saved revision.
- **Follow-ups after testing.**
  - Render follows the latest generated revision: a render of an older revision leaves
    step 3 current, with "Last render: Rev A (job #5)…", and the Renders tab labels it
    "older revision". A queued or running job is in progress, not done, and a failed one
    shows its error.
  - One shared events stream per job (`useRenderJob`) feeds the stepper, the Renders tab
    and the chat card, so "Render job #N" updates live.
  - A card opened from the panel says so next to its button, with a link that scrolls to
    the card and focuses Confirm.
  - The name check reserves its worst-case height only once the field has text, and never
    shrinks while typing.
  - Out-of-date files show step 2 in amber instead of ✓.
