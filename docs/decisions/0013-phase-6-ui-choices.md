# 0013: Phase 6 UI choices

**Status:** accepted (2026-11-18). Details of the Phase 6 React UI, plus small deviations from
`PLAN.md`.

## Context

Phase 6 builds the studio (chat, parameter panel, 3D viewer, drawing and render tabs), the
catalog view and the "How this demo works" guide, with vitest tests and one Playwright
end-to-end test on the FakeClient. Before this phase, the backend had the assistant, the gate
and the render routes, but none of the routes a panel or a catalog needs.

## Decisions

1. **New read-only routes for the UI.** None of them has a side effect, so the gate
   (`POST /api/actions/{id}/confirm`) is still the only way to reserve, write or queue.
   - `GET /api/families` and `GET /api/families/{code}?lang=`: the parameters in schema
     order, with ranges, steps, units and rule ids, plus the colors or finishes with their
     hex. `family_info` is shared with the `describe_family` tool.
   - `POST /api/validate` and `POST /api/preview`. Both ask `standards/validators.py`
     (invariant 1). The preview builds the GLB in memory and keeps it in the same LRU cache
     as `preview_geometry`, through the shared `build_preview`. Nothing goes under
     `DESIGNS_ROOT`.
   - `GET /api/catalog`: SAP materials through `SapClient`, each with the revisions that
     have files. When SAP is down it answers 502. Folders without a SAP record are not
     listed.
   - `GET /api/designs/{sku}/{rev}` and `/files/{step|stl|glb|drawing}`: the SKU and the
     revision are validated before they become path segments (invariant 4).
   - `GET /api/gallery` and `/api/gallery/{file}`: only files named in
     `docs/gallery/manifest.json`.
2. **The panel validates through the preview route.** Edits are debounced by 350 ms, and
   one `POST /api/preview` returns both the validation and, when the parameters are valid,
   the model. A preview the assistant already built is put into the query cache under the
   same parameters, so the viewer shows it without a rebuild. Query keys sort the parameter
   names.
3. **Proposed values stay highlighted.** A `parameter_proposal` fills the panel and marks
   those parameters in amber until the designer edits them. The chat sends the panel with
   each message as data (decision 0012).
4. **The viewer's color and finish switch edits the parameter.** A view-only toggle would
   show one color in 3D while the panel and the drawing said another, so the switch edits
   the parameter and there is one source of truth. The viewer's glass is a real-time
   approximation (`MeshPhysicalMaterial` with IOR 1.47 and local light formers, no
   environment map download). The Blender renders are the reference.
5. **Violation messages stay in English.** Labels, units and the UI are translated. The
   validators' messages are written once, in English, and the rule id and nearest valid
   values carry the meaning in both languages. Translating the messages would mean a
   second copy of every rule text. Phase 7 can revisit this if the Spanish scenarios need
   it.

   **Revised 2026-11-19 (UI polish):** each `Violation` now also carries `message_es`,
   written next to the English text with the same computed numbers. The panel shows it in
   the Spanish UI (`/api/validate` and `/api/preview` send it). The agent still gets only
   the English message, because it answers in the designer's language itself. A test checks
   that every `Violation(...)` in the rule code passes `message_es`.
6. **No router.** Studio and Catalog are two views behind one state, so the conversation
   and the panel survive a switch between them. There is no new dependency.
7. **The demo guide follows the `portfolio-demo-guide` skill, adapted.**
   - Only the in-app banner is used, because there is no landing page.
   - "You are here" follows the design flow (describe → parameters → reserve → generate
     → render) instead of a URL.
   - The product link points to the Product Design Manual.
   - The guide keeps its neutral zinc style, not the H&L colors.
8. **H&L theme.** The shadcn tokens use the logo's colors (navy `#18204a`, cobalt
   `#2f45b5`, sea green, amber, rose). The logo is copied to `frontend/public/hl_logo.svg`.
9. **New frontend dependency: `radix-ui`**, which the shadcn components need (button,
   card, tabs, input, select, badge, scroll-area, tooltip). The shadcn CLI also added an
   unrelated npm package called `cn` and imported from it. That package was removed, and
   the components use `@/lib/utils`.
10. **End-to-end test.**
    - `e2e/` is its own npm package with `@playwright/test` and Chromium.
    - `scripts/e2e_server.py` runs the real backend with three stand-ins:
      - the in-memory SAP from `backend/tests/fake_sap.py`;
      - `backend/tests/fake_blender.py` instead of Blender;
      - a FakeClient whose script is picked by keywords in the designer's message.
    - Vite's proxy target is read from `BEAD_API_URL`, so the test runs next to a dev
      backend on port 8000 without clashing.
    - `E2E_SCREENSHOTS=<folder>` saves a screenshot at each step.
    - CI runs it in a new `e2e` job.

## Consequences

- The UI decides nothing. Validity, measurements and the cards' effects all come from the
  backend, so the tests check what the UI shows, not rules.
- The e2e flow covers the whole Phase 6 path, every side effect behind its click:
  description → proposed parameters → a GB-05 violation fixed with the nearest valid
  value → reserve → files and drawing → render → catalog.
- The viewer chunk (three.js and drei) is about 1.07 MB minified. It loads lazily, after
  the first paint.
