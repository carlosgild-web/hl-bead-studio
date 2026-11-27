# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.1.0] - 2026-11-27

Phase 10 of [`PLAN.md`](PLAN.md): the README video, the full-flow GIF and the README to the
portfolio standard.

### Added

- `start.cmd video` / `./start.sh video`: every video take runs on fresh seed data in
  `data-video/` (designs and the mock SAP), with 16 render samples; `data/` is never touched
  (decision 0026).
- The README video, a real model under the hood: `video/` records the app with Groq
  `openai/gpt-oss-120b` beside an "Under the hood" panel (the code and the data behind each
  step, the manual search's own FTS5 terms and ranking), cuts model waits over 3 s with a
  label, and ends with the STEP file in FreeCAD while Blender renders. Ported from
  hl-create-design (decision 0027); what it shows and how to record it again in
  [`docs/video.md`](docs/video.md).
- The README GIF of the whole flow, from one sentence to the drawing and the render gallery
  (`npm run showcase:gif` in `e2e/`), and showcase shots of the 3D viewer, the Drawing tab and
  the Renders tab.
- `docs/assistant.md`, `docs/studio-ui.md`, `docs/development.md`, `docs/online-safety.md`,
  and `scripts/check_links.py` for the relative links, images and anchors in the docs.
- Groq run 1 part 3: the last 8 core scenarios, 7 passed. The run is complete at 14/30; the
  safety checks held in all 30.

### Changed

- The README follows the portfolio standard: badges, the video, a quick start, "What this
  demonstrates", "Before and after", the nine invariants with the file and the tests that
  enforce each, one evaluation table, a screenshot grid, "What each feature needs", and test
  counts from a real run. The long sections moved to `docs/`.
- The LinkedIn post and video script drafts left the repo.

## [1.0.0] - 2026-11-26

The first release: Phases 0 to 9 of [`PLAN.md`](PLAN.md).

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
  - The eval saves its report after every scenario, and marks a run that stopped early as
    incomplete. Real runs on Ollama (16/30), Groq (7/22, incomplete) and Dahl (23/30).
- Phase 8 packaging and providers (decisions 0016–0021):
  - Two cloud providers through one OpenAI-compatible client: Dahl (`DAHL_*`, default model
    `zai-org/GLM-5.3-Flash`) and Groq's free tier (`GROQ_*`), with retries on per-minute
    limits and a clean stop at a daily limit (the eval stops there and `--start-at`
    continues).
  - A fallback for cloud providers (`LLM_FALLBACK`, default `ollama,fake`): without a key,
    or at a daily limit, the studio uses Ollama if it answers, else demo mode, and stays on
    it until it restarts.
  - `python -m app.cli llm-check` and `LLM_PROVIDER=auto`: probe Dahl, Groq and Ollama at
    launch, suggest one and ask (start scripts), or choose without questions (`auto`, the
    Docker default). One 429 classifier for the check and the clients.
  - `python -m app.cli free-ports`: the launchers show what holds ports 8000, 8100 and 5173
    and offer to stop it.
  - A Docker image and `compose.yaml` (the app and the mock SAP; Ollama in an optional
    profile), with the backend serving the built frontend (`FRONTEND_DIST`).
  - The UI: a Workflow stepper, a next-step chip that works without the LLM, a warning when
    the drawing is out of date, the next free revision (`next_rev`), the product name field
    that adds the family word and checks the name while typing, and rule messages in
    Spanish in the Spanish UI.
- Phase 8b demo mode (decision 0022):
  - The Q&A bank (`docs/qa/qa_bank.json`, 46 entries in English and Spanish) with content
    tests that keep it true to the manual.
  - Demo mode answers from the bank (`DemoClient`): a design request fills the panel
    through the real `propose_parameters`, a question about the manual is answered after a
    real manual search, and anything else gets a bilingual fallback. It never opens a card.
  - A "Demo mode" badge and two question chips in the chat; why `auto` fell to demo mode is
    `llm_note` in `/api/health`.
  - The `qa` eval suite (`agent-eval --suite qa|all`, 92 scenarios; `--variants` adds the
    phrasing variants). CI runs `--fake --suite all --variants` (183 scenarios).
- A "New design" button in the chat header, and a "Start a new design" next-step chip once
  the render is finished: the chat and the panel start over (reserved SKUs, files and renders
  stay saved), with an inline confirmation.
- Focus mode: while a confirmation card or the Start-over question waits for the designer, the
  rest of the studio is grayed, slightly blurred and inert, and the card gets the keyboard
  focus. "Use the chat" (or Esc) sets a card or a workflow step aside and puts the cursor in
  the chat; "Go to the card" in the stepper, now shown for any waiting card, brings it back.
- After a confirmed reserve or generate, the workflow opens the next step and the studio
  waits there; the chat's next-step chip opens the same step.
- The studio session (conversation, panel, view) survives a reload, and file downloads stay
  on the page.
- SAP's current revision follows the generated files, and revisions never skip a letter
  (decision 0024).
- `python -m app.cli demo-reset` returns the demo to the seed catalog: test SKUs, designs,
  renders and conversations are removed (decision 0024).
- A SKU can be reserved while the design breaks rules; the card warns and lists them
  (decision 0025). A generate card lists the design it will write.
- Rule ids link to the manual; rule messages sit under their field and name it as the panel
  does. The catalog search also filters the gallery and can be cleared.
- A render shows the elapsed time instead of a progress bar that looked stuck.
- Phase 9 showcase: the README with a GIF, screenshots, the drawing, renders, the
  architecture and an eval summary; `npm run showcase` in `e2e/` makes the images again
  (`e2e/tests/showcase.spec.ts`, not part of `npm test`); the Dahl `qa` suite results
  (81/92) in `docs/eval/`.

### Changed

- The in-memory SAP stand-in moved from `backend/tests/fake_sap.py` to
  `backend/app/sap/memory.py` (`InMemorySap`), for the eval harness.
- The chat shows the backend's reason when a turn is refused (rate limit, token cap).
- Demo mode no longer gives the same English notice to every message (decision 0022).
- The Spanish UI says "dije" for charm, as the manual does.
- Demo mode proposes the values in the designer's message, in the designer's language
  (decision 0023), and recognizes a question without a question mark.
- The studio fits the screen; the chat header wraps, and phones get a compact header.
  Choices read as words everywhere (no internal keys).
- Charm height reads as the body height, and initials are capitals.

- Manual and schemas after measuring the fonts (decision 0010): CH-07 minimum heights
  (Pacifico 10.5 mm, Y 18.5 mm; Cinzel Bold 16.5 mm, no K), CH-06 engraved letters at least
  3.0 mm and letter-spaced, disc default diameter 20.0 mm, new rule CH-08 (crescent
  proportions).

### Fixed

- The 3D viewer shows charms with the loop up; rhodium shows against a slate backdrop, and
  glass keeps its color in the lower facets.
- An initial hangs from its center of mass.
- The drawing says "Mass" for glass beads; "before plating" only for charms.
- The panel's live check is not retried after a refusal and is cancelled when stale.
- Metal renders get a soft gradient instead of a black band (the gallery was re-rendered).
- Opening a card that was already open (the stepper twice, or the next-step chip and the
  stepper) showed it twice in the chat; the server returns the same card, so the chat now
  shows it once and scrolls to it.
- Settings failed to read `ANTHROPIC_API_KEY` from the environment in any process that had
  imported CadQuery (its multimethod dispatch makes `typing.Union` look like a sequence to
  pydantic-settings).
- A validation with missing parameters listed each one several times.
- The false-card-claim check corrected right answers that only mentioned a card ("you
  cancelled the confirmation card"); it now looks for a card said to be shown or waiting,
  outside a negative or conditional clause (found by the eval).
- The revision argument of the generate and render tools lists the GEN-02 letters (a model
  offered revision I in the eval).
- Groq's last call sends the history as plain text, so gpt-oss answers instead of calling a
  tool (HTTP 400).
- The 3D viewer: clearer glass, fully metallic plating, and a flat metal face that is never
  black.

[Unreleased]: https://github.com/carlosgild-web/hl-bead-studio/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/carlosgild-web/hl-bead-studio/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/carlosgild-web/hl-bead-studio/releases/tag/v1.0.0
