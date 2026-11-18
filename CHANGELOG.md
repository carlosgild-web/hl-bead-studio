# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Phase 0 skeleton: backend and sap-mock FastAPI packages with health endpoints, Vite React
  TypeScript frontend (Tailwind, shadcn/ui, react-three-fiber), CI, decision records 0001–0007.
- Phase 1 company content: Product Design Manual in English and Spanish (rules GEN-01…04,
  GB-01…07, CH-01…07), JSON Schemas for the seven families, approved glass colors, finishes
  and materials, SAP seed (luna's 10 products plus 15 fictional ones), the H&L logo for the
  title block, content tests and decision 0008.
- Phase 2 mock SAP service `ZHL_MM_MATERIAL_SRV`: OData v2 material lookup, `$filter`,
  `$top`/`$skip`, `$metadata`, SKU reservation (next number per type, atomic, never
  reissued), Basic auth, CSRF handshake, SAP-style errors, chaos switches and curl examples.
- Phase 3 geometry, drawing and validation: `standards/validators.py` checks every manual rule
  and returns each violation with its rule id and the nearest valid values; one CadQuery
  builder per family with STEP, STL and GLB export, volume and mass; the CH-03 smallest-feature
  check on charm outlines (shapely); technical drawings with OpenCascade hidden-line views and
  the H&L title block, rendered to PDF in Python (decision 0009, after a failed TechDraw
  spike); confined design folders, an audit log and the `validate`, `generate` and
  `measure-fonts` CLI commands; the OFL fonts in `cad/fonts/`; showcase drawings in
  `docs/showcase/`; property-based geometry tests (Hypothesis).
- Phase 4 Blender renders (decisions 0003 and 0011): `blender/render.py` builds a studio scene
  (seamless backdrop, three soft boxes, a turntable camera rig) around the GLB and renders a
  1024 px PNG with Cycles on the CPU and OpenImageDenoise. It uses glass with IOR 1.47 and the
  approved color, or gold, rhodium or antique bronze plating. A SQLite render queue with one
  in-process worker, an atomic claim, recovery after a restart and audit rows. A bounded
  Blender subprocess with a timeout and a captured log. Read-only render routes with
  server-sent events. A `render` CLI command. `scripts/build_gallery.py` and the WebP gallery
  in `docs/gallery/`. `RENDER_SAMPLES` and `RENDER_TIMEOUT_S` settings. A `blender` pytest
  marker.
- Phase 5 LLM layer and agent (decisions 0004, 0005 and 0012):
  - `LLMClient` with `OllamaClient` (native tools, recovers tool calls written as text),
    `AnthropicClient` (Messages API over httpx, no SDK) and a scripted `FakeClient`.
  - A bounded tool loop with twelve tools, an EN/ES system prompt and a trace per run.
  - The confirmation gate `POST /api/actions/{id}/confirm`: validates again, runs at most
    once, actions expire, every action is audited.
  - `POST /api/chat` (server-sent events), plus conversation, run, action and preview GLB
    routes.
  - `SapClient` (Basic auth, the CSRF handshake, OData v2), FTS5 search over the manual with
    rule ids, and the GEN-03 product name check.
  - The `chat`, `confirm` and `cancel` CLI commands.
  - Scripted conversations and prompt-injection tests on Fake.
  - A backend check that corrects answers claiming a confirmation card that was never
    opened.
- Phase 6 React UI (decision 0013):
  - The studio: a streaming chat with collapsed tool steps and confirmation cards; the
    parameter panel with values the assistant proposed highlighted, live validation with
    rule ids and nearest-value buttons; a three.js viewer of the model with the glass color
    or plating finish and its measurements; drawing (PDF and STEP/STL/GLB downloads) and
    render tabs with live job progress and the gallery.
  - The catalog view: SAP materials, the new SKUs and their drawings.
  - H&L brand colors, ES/EN, and the "How this demo works" guide.
  - Read-only backend routes: families, validate, preview, catalog, design files and
    gallery.
  - "Reserve SKU…", "Generate files…" and "Render…" in the parameter panel open the
    confirmation cards without the assistant, through `POST /api/actions` with the same
    checks as the assistant's tools (decision 0014).
  - A "Next step" button in the chat after each confirmed card.
  - `start.cmd` and `start.sh`: start the mock SAP, the backend and the UI, and open the
    browser, with an optional LLM provider argument.
  - Vitest tests for the state and the flow, and a Playwright end-to-end test on the
    FakeClient (`e2e/`, `scripts/e2e_server.py`) that also runs in CI.
- Phase 7 evaluation and hardening (decision 0015):
  - `python -m app.cli agent-eval`: 30 scenarios (valid designs, one per broken rule, the
    reservation, generation and render flow, cancel, names, revision letters, SAP down,
    Blender missing, prompt injection; English and Spanish) run through the real agent and
    confirmation gate, with the in-memory SAP. A scorer checks the parameters, the cited rule
    ids, the cards, and that no side effect happened without a click. It reads the traces and
    the side effects, never the model's own words.
  - `--fake` runs the ideal scripts and must pass 100% in CI; tests show that a bad model
    fails the right check. Real runs on Anthropic and Ollama, failures included, in
    `docs/eval/`.
  - Online safety: `RATE_LIMIT_PER_MINUTE` per client on chat, card actions and previews
    (HTTP 429 with `Retry-After`); `DAILY_TOKEN_CAP` for the assistant; and
    `DESIGNS_RETENTION_HOURS`, which deletes old generated designs and their renders and
    writes an audit row for each.
  - The render tool and the click say at once when Blender is not installed (HTTP 503 on
    the click, `renders` in `/api/health`), instead of queuing a job that can only fail.

### Changed

- The in-memory SAP stand-in moved from `backend/tests/fake_sap.py` to
  `backend/app/sap/memory.py` (`InMemorySap`), for the eval harness.
- The chat shows the backend's reason when a turn is refused (rate limit, token cap).

- Manual and schemas after measuring the fonts (decision 0010): CH-07 minimum heights
  (Pacifico 10.5 mm, Y 18.5 mm; Cinzel Bold 16.5 mm, no K), CH-06 engraved letters at least
  3.0 mm and letter-spaced, disc default diameter 20.0 mm, new rule CH-08 (crescent
  proportions).

### Fixed

- Settings failed to read `ANTHROPIC_API_KEY` from the environment in any process that had
  imported CadQuery (its multimethod dispatch makes `typing.Union` look like a sequence to
  pydantic-settings).
- A validation with missing parameters listed each one several times.
- The false-card-claim check corrected right answers that only mentioned a card ("you
  cancelled the confirmation card"); it now looks for a card said to be shown or waiting,
  outside a negative or conditional clause (found by the eval).
- The revision argument of the generate and render tools lists the GEN-02 letters (a model
  offered revision I in the eval).
