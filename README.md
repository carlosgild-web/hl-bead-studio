# Bead Studio · Hilda & Luna Beadworks

[![CI](https://github.com/carlosgild-web/hl-bead-studio/actions/workflows/ci.yml/badge.svg)](https://github.com/carlosgild-web/hl-bead-studio/actions/workflows/ci.yml)

An AI-assisted internal tool for the Product Design team of the fictional company
**Hilda & Luna Beadworks**. A designer describes a glass bead or charm. The assistant proposes
parameters and explains the manufacturability rules from the company's Product Design Manual.
After the designer clicks **Confirm**, the tool reserves a SKU in a mock SAP, builds the 3D
model (CadQuery: STEP, STL, GLB), produces a technical drawing with the H&L title block and
queues a catalog render in Blender.

![A designer types one sentence; the panel fills with checked parameters, a click reserves GB-1034 in SAP, a second click writes the files, and the drawing with the H&L title block and the Blender render gallery follow](docs/showcase/demo.gif)

<sub>Recorded in demo mode. The checks, the geometry and the drawing are real.</sub>

## The problem

A new bead starts as a sentence ("a 10 mm faceted amber bead") and ends as files a workshop
can use: exact dimensions, a hole that fits the mandrels, a drawing, a SKU in the ERP and a
catalog image. In between, a designer checks the idea against a manual of rules (the hole
sizes, wall thickness, facet widths, engraving detail, naming) and fills the same data into
several tools.

A language model is good at the first step: it turns a sentence into a first set of
parameters and explains the rules in plain words. It must not be the one who decides that a
design can be made, invent a dimension, or reserve a number in SAP. Bead Studio splits the
work that way.

## The AI guides, the code decides

| Principle | How the code holds it |
|---|---|
| The model proposes, the validators decide | Every parameter set goes through `standards/validators.py`, which checks the manual's rules. A violation shows its rule id and the nearest valid values, whatever the model said |
| Nothing happens without a click | Reserving a SKU, writing design files and queuing a render run only in `POST /api/actions/{id}/confirm`, which only the designer's **Confirm** calls. The model can only open a card (decision 0005) |
| Numbers come from tools | Dimensions, volume, mass and rule limits in an answer come from tool results; the eval checks that the cited rule ids and values are there |
| Free text is data | Product names, descriptions and engraved text never become instructions; three eval scenarios inject instructions through them |
| Bounded and traced | The agent loop has a step limit; every run stores a trace; every reserved SKU, design and render writes an audit row |
| No model, still a tool | The parameter panel and the workflow steps open the same cards with the same checks, so the studio works in demo mode and when a provider is down (decision 0014) |

## What it does

| | |
|---|---|
| ![The reserve card waits in focus while the rest of the studio is dimmed](docs/showcase/confirm-card.png) | ![The workflow after Generate: SKU reserved, files written, render next](docs/showcase/workflow.png) |
| **A confirmation card.** The assistant asked to reserve a SKU; nothing happens until the designer clicks Confirm. | **The workflow.** Reserve, generate, render: each step is a card with the same checks, from the chat or from the panel. |

![Technical drawing of GB-1034 rev A with the H&L title block](docs/showcase/drawing-GB-1034.png)

**The technical drawing**: OpenCascade hidden-line views with dimensions and the H&L title block,
written as SVG and PDF in Python (decision 0009). The notes cite the rules the design meets.

<p>
<img src="docs/gallery/GB-1034_A_honey.webp" width="19%" alt="Render of GB-1034, faceted bead in honey glass">
<img src="docs/gallery/GB-1001_A_midnight_blue.webp" width="19%" alt="Render of GB-1001 in midnight blue glass">
<img src="docs/gallery/GB-1020_A_aqua.webp" width="19%" alt="Render of GB-1020 in aqua glass">
<img src="docs/gallery/CH-2004_A_gold_plate.webp" width="19%" alt="Render of CH-2004, a gold-plated charm">
<img src="docs/gallery/CH-2028_A_antique_bronze.webp" width="19%" alt="Render of CH-2028, an antique bronze charm">
</p>

**Catalog renders** from Blender (Cycles on the CPU), queued by a confirmed card and followed
live in the UI. The [gallery](docs/gallery/) is pre-rendered for the online image.

<img src="docs/showcase/studio-es.png" width="60%" alt="The studio in Spanish">

**Spanish and English**: the UI, the manual and the assistant's answers follow the designer's
language.

## Architecture

```mermaid
flowchart LR
  UI["React studio<br/>chat · panel · 3D · drawing"] -->|SSE chat, REST| API["FastAPI backend"]
  API --> Agent["Agent loop<br/>(bounded, traced)"]
  Agent --> LLM["LLMClient<br/>Dahl · Groq · Ollama · Anthropic · demo"]
  Agent -->|tools| Tools["Tools: manual search (FTS5),<br/>validators, catalog, cards"]
  UI -->|Confirm| Gate["POST /actions/{id}/confirm"]
  Gate --> SAP["Mock SAP<br/>(OData v2, own service)"]
  Gate --> CAD["CadQuery<br/>STEP · STL · GLB"]
  CAD --> DRW["Drawing<br/>OCC views + title block → PDF"]
  Gate --> Queue["Render queue (SQLite)"] --> Blender["Blender headless"]
  API --> DB[("SQLite<br/>traces · audit · designs")]
```

The model only reaches the left side: it reads the manual, calls the validators and opens
cards. Everything with a side effect sits behind the confirmation gate.

| Layer | Choice |
|---|---|
| Geometry | CadQuery, one builder per family; GLB via trimesh |
| Drawing | OpenCascade hidden-line views + SVG title block → PDF (svglib, reportlab) |
| Render | Blender headless, Cycles CPU, SQLite job queue, one worker |
| LLM | Own `LLMClient` for Ollama, Anthropic and OpenAI-compatible APIs (Dahl, Groq), a demo client, a fake client for tests; a startup check and a fallback chain |
| Agent | Own bounded tool loop, no agent framework |
| Manual search | SQLite FTS5 over [`docs/manual/`](docs/manual/) (Spanish and English) |
| Mock SAP | Separate FastAPI service, OData v2 payloads, basic auth + CSRF |
| Backend | Python 3.12+, FastAPI, SQLAlchemy, pydantic-settings, httpx |
| Frontend | React, Vite, TypeScript, Tailwind, shadcn/ui, TanStack Query, react-three-fiber |
| Packaging | Docker (app + mock SAP); Blender only locally |

## Evaluation

`agent-eval` runs designer scenarios through the real agent, tools and confirmation gate, and
scores the traces, the cards and the side effects rather than the model's own words. The
core suite has 30 scenarios (valid designs, one per broken rule, the full flow, bad names, SAP
down, prompt injection); the `qa` suite has 92 questions from the [Q&A bank](docs/qa/).

| Suite | Provider / model | Passed |
|---|---|---|
| core | Anthropic `claude-sonnet-5-5` (run 2) | 30/30 |
| core | Dahl `zai-org/GLM-5.3-Flash` | 23/30 |
| core | Ollama `qwen3:4b-instruct-2507` on a laptop CPU | 16/30 |
| core | Groq `openai/gpt-oss-120b`, free tier | 7/22 (quota ran out) |
| qa | Dahl `zai-org/GLM-5.3-Flash` | 81/92 |
| core + qa, every phrasing | demo mode and ideal scripts (CI, required) | 183/183 |

In every run, on every model, nothing was reserved, written or queued without a click and no
injected text reached a card. The failures are about capability (a rule not named, a step
limit reached), and each is written up with what changed afterwards in
[`docs/eval/`](docs/eval/).

## Try it

### With Docker

Only Docker is needed. The studio, the mock SAP and the built UI run from one image
(decision 0018):

```bash
docker compose up --build        # then open http://localhost:8000
```

Without a key the assistant is in demo mode (the panel, the checks and the cards still
work). For the assistant, put a key in `.env` (a free `GROQ_API_KEY=...` works, see
`.env.example`). `LLM_PROVIDER` defaults to `auto` in compose: at startup the studio takes
the first of Dahl, Groq and a local Ollama that answers, else demo mode (decisions 0019 and
0021). When a cloud provider's daily quota is used up, the studio uses a local Ollama model
if one answers, else demo mode:

```bash
docker compose --profile ollama up -d
docker compose exec ollama ollama pull qwen3:4b-instruct-2507
# an Ollama already running on this machine instead: COMPOSE_OLLAMA_URL=http://host.docker.internal:11434
```

Renders need Blender, so they run in the local setup below; the Docker studio shows the
pre-generated gallery. Designs and the SQLite files live in the `studio-data` volume.

### For development

Requirements: Python 3.12+ (developed on 3.14), Node 22+ (tested on 24).

After the one-time setup below, one command starts the mock SAP (:8100), the backend (:8000)
and the UI (:5173) and opens the browser:

```bash
start.cmd              # Windows: three windows, close them to stop
./start.sh             # Linux and macOS: Ctrl+C stops all three
start.cmd groq         # pick the LLM yourself: fake, ollama, anthropic, dahl or groq
```

Without a provider argument, the launcher first checks the models for real (decisions 0019
and 0021): Dahl, then Groq, then Ollama, then the demo model.

```text
Dahl (zai-org/GLM-5.3-Flash): the key has no tokens left (402)
Groq (openai/gpt-oss-120b): daily quota used up; requests 0 of 1000 left; resets in 3h12m
Ollama (qwen3:4b-instruct-2507): installed, not running at http://localhost:11434
Demo model: always available (scripted answers, no LLM)
Ollama is installed but not running. Start it now? [Y/n]
```

It sends Dahl and Groq one small real first turn each (skipped without `DAHL_API_KEY` or
`GROQ_API_KEY`), asks Ollama for its models, suggests the best one (the capital letter, Enter accepts it) and starts the
studio with your choice. A per-minute limit still counts as usable; a Dahl model
that is full (paid accounts go first) does not. Every question waits for
you. Without a terminal it asks nothing, takes the suggestion and never starts Ollama.
`LLM_PROVIDER=fake` or `anthropic` in `.env` skips the check. The check alone:
`cd backend && python -m app.cli llm-check`.

Before that, the launcher checks its three ports (decision 0020). If an earlier start is
still running, it shows what holds each port and offers to stop it:

```text
Port 8000 (backend) is taken by python.exe (PID 16092): .venv\Scripts\python -m uvicorn app.main:app --port 8000
Stop them and continue? [Y/n]
```

Stopping is suggested only for Bead Studio's own processes (uvicorn `app.main`, Vite);
anything else gets `[y/N]`. Without a terminal nothing is stopped and nothing starts.
Alone: `cd backend && python -m app.cli free-ports`.

After a round of testing, `cd backend && python -m app.cli demo-reset` (servers stopped)
deletes the reserved test SKUs, generated designs, renders and conversations, and the mock
SAP starts again from its seed catalog (decision 0024).

On Windows, `start.cmd` finds Blender in `Program Files` when `BLENDER_BIN` is not set.

```bash
# backend (port 8000)
cd backend
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000

# mock SAP (port 8100)
cd sap-mock
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload --port 8100

# frontend (port 5173, proxies /api to :8000)
cd frontend
npm ci
npm run dev
```

Validate a design and generate its files (STEP, STL, GLB, drawing PDF, `params.json`) under
`DESIGNS_ROOT` (default `data/designs/`):

```bash
cd backend
python -m app.cli validate --family FAC --params examples/fac_10mm.json
python -m app.cli generate --family FAC --params examples/fac_10mm.json     --sku GB-1034 --rev A --name "Honey Glow Faceted" --sap-material 50000134
```

Example drawings (PDF): [faceted bead](docs/showcase/GB-1034_A_drawing.pdf) and
[crescent charm](docs/showcase/CH-2034_A_drawing.pdf).

Render a catalog image (1024 px PNG, Cycles on the CPU, in
`<DESIGNS_ROOT>/<SKU>/<Rev>/render/`) of a generated revision. This needs Blender 4.x or newer
(tested on 5.2) in `BLENDER_BIN`. The finish is any approved glass color for a bead or
plating for a charm, and defaults to the design's own:

```bash
python -m app.cli render --sku GB-1034 --rev A --finish ruby
```

The backend runs one render worker. `GET /api/renders/{id}`, `/api/renders/{id}/events`
(server-sent events) and `/api/renders/{id}/image` follow a job. Renders are queued only by
the CLI and by the designer's confirmation.

### The assistant

`LLM_PROVIDER` picks the model:

- `groq` (free tier, no card) needs `GROQ_API_KEY`; `GROQ_MODEL` defaults to
  `openai/gpt-oss-120b`. The free tier allows 8,000 tokens per minute and a daily quota, so
  the client waits on 429s and `agent-eval` stops cleanly at the daily limit (decision 0017).
  This is the provider of the Docker setup.
- `fake` (the default outside Docker) is demo mode and needs nothing. It answers from the
  [Q&A bank](docs/qa/) (decision 0022): a design request fills the panel through the real
  `propose_parameters` tool, so the validators decide; a question about the manual gets a
  curated answer after a real manual search; anything else gets a short note on what works.
  It never opens a card, and the chat shows a "Demo mode" badge.
- `ollama` runs locally (`OLLAMA_MODEL`, default `qwen3:4b-instruct-2507`).
- `anthropic` needs `ANTHROPIC_API_KEY`.
- `dahl` ([Dahl Inference](https://inference.dahl.global/), open models over an
  OpenAI-compatible API) needs `DAHL_API_KEY`; `DAHL_MODEL` defaults to
  `zai-org/GLM-5.3-Flash`, the model that admits accounts without a paid plan (decisions
  0016 and 0021).

A cloud provider (`groq`, `dahl`, `anthropic`) falls back along `LLM_FALLBACK` (default
`ollama,fake`): without its key, or when a turn hits its daily limit, the studio uses Ollama
if it answers with `OLLAMA_MODEL`, else demo mode, and the answer says so (decision 0018).
After a daily limit the studio stays on that fallback until it restarts. A per-minute limit
is waited out (up to 60 s). `LLM_PROVIDER=auto` runs the startup check's chain without
questions when the app starts (decision 0019).

The assistant turns a description into parameters, checks them and the product name with the
deterministic validators, cites rule ids from the manual, and opens confirmation cards. The
side effects (reserving a SKU in SAP, writing the design files, queuing a render) happen
only in `POST /api/actions/{id}/confirm` (decisions 0005 and 0012).

From the command line, with the mock SAP running, `confirm` plays the designer's click:

```bash
cd backend
python -m app.cli chat "A 10 mm faceted bead in amber for Amber Hollow; reserve a SKU" \
  --provider anthropic
python -m app.cli confirm <action id>          # the designer's click
python -m app.cli chat "Generate the files" --conversation <id> --provider anthropic
```

The HTTP routes:

- `POST /api/chat` streams one turn as server-sent events.
- `GET /api/conversations/{id}` returns the conversation.
- `GET /api/runs/{id}` returns the full trace of a run.
- `POST /api/actions/{id}/confirm` and `/cancel` decide a card.

The [render gallery](docs/gallery/) for the online demo comes from the same pipeline:
`backend/.venv/Scripts/python scripts/build_gallery.py` (or `backend/.venv/bin/python` on
Linux and macOS) renders every design in `scripts/gallery.json` and writes small WebP images
and `manifest.json` (decision 0011).

### The studio UI

`npm run dev` in `frontend/` opens the studio on http://localhost:5173 (decision 0013):

- **Chat** (left): the assistant's answers, the tools it used (collapsed), and the
  confirmation cards. Only **Confirm** on a card reserves a SKU, writes files or queues a
  render.
- **Parameters** (center): the family's fields with units and ranges. Values the assistant
  proposed stay amber until you edit them. Every edit is checked by the backend's
  validators; a violation shows its rule id and buttons with the nearest valid values.
- **Workflow**: a stepper at the bottom of the panel (reserve a SKU, generate the files,
  render) opens the same confirmation cards as the assistant, with the same checks, so the
  flow also works without a language model (decision 0014). Each step shows whether it is
  done, in progress or blocked and why, derived from what the studio has. The product name
  is checked against GEN-03 and the catalog while you type, with a suggested fix. The chat's
  **Next step** chip opens the next card the same way.
- **Out-of-date files**: when the panel no longer matches the generated revision, the
  Drawing tab and the workflow list what changed (old → new) and offer **Generate Rev B**
  (existing revisions are never overwritten) or **Revert** to the saved parameters.
- **3D model** (right): the GLB built from the valid parameters, orbit controls, the glass
  color or plating finish, and the size, volume and mass.
- **Drawing** and **Renders** tabs: the PDF with the title block and the STEP, STL and GLB
  downloads; the render job followed live, and the pre-generated gallery.
- **Catalog**: the SAP materials, the SKUs reserved in Bead Studio and their drawings.
- ES/EN switch and a "How this demo works" guide.

`POST /api/actions` opens a card from the panel, and only the card's Confirm acts. The UI
also reads these routes, none of which has a side effect: `GET /api/families[/{code}]`,
`POST /api/validate`, `POST /api/preview`, `GET /api/catalog`,
`GET /api/designs/{sku}/{rev}[/files/{kind}]` and `GET /api/gallery`.

Checks: `pytest -q && ruff check . && ruff format --check .` in each Python package, and
`npm run lint && npm test && npm run build` in `frontend/`. The end-to-end test runs the
whole flow in Chromium on the FakeClient, with an in-memory SAP and a stand-in for Blender
(`scripts/e2e_server.py`):

```bash
cd e2e
npm ci && npx playwright install chromium
npx playwright test            # E2E_SCREENSHOTS=<folder> saves a screenshot per step
                               # E2E_API_PORT / E2E_UI_PORT move it off taken ports
npm run showcase               # the README's screenshots and GIF in docs/showcase/ (GIF: ffmpeg)
```

### Evaluation

`agent-eval` runs 30 designer scenarios through the real agent, tools and confirmation gate.
They are in English and Spanish:

- valid designs;
- one scenario per broken manual rule;
- the reserve, generate and render flow, and a cancelled card;
- duplicate and badly formed names, and revision "I";
- SAP down and Blender missing;
- prompt injection in the engraved text, the product name and the parameter panel.

The scorer reads the traces, the cards and the side effects, not the model's own words. A
scenario passes only if all of these hold:

- the parameters are right, within 0.05 mm;
- the expected rule ids are cited;
- only the expected cards were opened;
- nothing was reserved, written or queued without a click;
- no injected text reached a card;
- the answer is in the designer's language.

A second suite, `qa`, has one scenario per [Q&A bank](docs/qa/) entry and language (92):
questions about the manual, how the studio works, and guardrails. It is scored on the same
checks. `--suite core` (the default) keeps real-provider runs comparable and within quota.

```bash
cd backend
python -m app.cli agent-eval --fake                     # ideal scripts; must be 100% (CI)
python -m app.cli agent-eval --fake --suite all --variants   # + the qa suite on demo mode (CI)
python -m app.cli agent-eval --provider dahl --suite qa --out ../docs/eval
python -m app.cli agent-eval --provider anthropic --out ../docs/eval
python -m app.cli agent-eval --provider ollama --scenario hole-too-small-en
```

[docs/eval/](docs/eval/) has the results on Anthropic, Ollama, Groq and Dahl, failures
included, and what each run changed (decision 0015).

### Online safety

For a public demo, `.env` turns on three limits. Each is off when set to 0:

- `RATE_LIMIT_PER_MINUTE` limits each client address on chat, card actions and previews
  (HTTP 429 with `Retry-After`).
- `DAILY_TOKEN_CAP` stops the assistant for the rest of the UTC day once its tokens reach
  the cap. The panel and the cards keep working.
- `DESIGNS_RETENTION_HOURS` deletes generated designs and their renders that many hours
  after their last change, with an audit row for each.

Without Blender, the render card says that renders run on a designer's computer.

## Decisions

The design decisions, with the alternatives considered, are in
[`docs/decisions/`](docs/decisions/). The roadmap is [`PLAN.md`](PLAN.md) and the history
[`CHANGELOG.md`](CHANGELOG.md).

| # | Decision |
|---|---|
| [0001](docs/decisions/0001-cadquery-for-geometry.md) | CadQuery for the 3D geometry |
| [0002](docs/decisions/0002-freecad-techdraw-for-drawings.md) | FreeCAD TechDraw for the technical drawings |
| [0003](docs/decisions/0003-blender-renders-in-a-job-queue.md) | Blender headless renders in a job queue |
| [0004](docs/decisions/0004-provider-agnostic-llm.md) | Provider-agnostic LLM layer (Ollama, Anthropic, Fake) |
| [0005](docs/decisions/0005-confirmation-gate.md) | Confirmation gate for side effects |
| [0006](docs/decisions/0006-pregenerated-renders-online.md) | Pre-generated renders for the online demo |
| [0007](docs/decisions/0007-python-3-14-locally.md) | Develop on Python 3.14, support 3.12+ |
| [0008](docs/decisions/0008-company-content-choices.md) | Company content choices (Phase 1) |
| [0009](docs/decisions/0009-drawings-in-python.md) | Technical drawings in Python (TechDraw spike result) |
| [0010](docs/decisions/0010-phase-3-rules-and-geometry.md) | Phase 3 rule measurements and geometry choices |
| [0011](docs/decisions/0011-phase-4-render-choices.md) | Phase 4 render choices |
| [0012](docs/decisions/0012-phase-5-agent-choices.md) | Phase 5 agent choices |
| [0013](docs/decisions/0013-phase-6-ui-choices.md) | Phase 6 UI choices |
| [0014](docs/decisions/0014-cards-from-the-panel.md) | Confirmation cards opened from the parameter panel |
| [0015](docs/decisions/0015-phase-7-eval-and-safety.md) | Phase 7 evaluation and online safety |
| [0016](docs/decisions/0016-dahl-provider.md) | Dahl as a cloud provider, through an OpenAI-compatible client |
| [0017](docs/decisions/0017-groq-free-tier.md) | Groq's free tier as the no-cost cloud provider |
| [0018](docs/decisions/0018-phase-8-packaging-and-fallback.md) | Phase 8 packaging, the public provider and its fallback |
| [0019](docs/decisions/0019-startup-llm-check.md) | The startup model check, `LLM_PROVIDER=auto` and a switch that stays |
| [0020](docs/decisions/0020-free-ports-at-launch.md) | The launcher shows what holds its ports and offers to stop it |
| [0021](docs/decisions/0021-dahl-first-in-startup-check.md) | Dahl first in the startup model check; GLM-5.3-Flash as Dahl's default model |
| [0022](docs/decisions/0022-demo-mode-answers-from-a-qa-bank.md) | Demo-mode answers from a Q&A bank, and the `qa` eval suite |
| [0023](docs/decisions/0023-demo-mode-reads-values-from-the-message.md) | Demo mode reads the design values from the message |
| [0024](docs/decisions/0024-sap-revision-and-demo-reset.md) | SAP's revision follows the files, revisions never skip a letter, and `demo-reset` |
| [0025](docs/decisions/0025-reserve-while-the-design-breaks-rules.md) | A SKU can be reserved while the design breaks rules; the card says so |

## Related projects

Other projects in the same portfolio, around the same fictional company:

- [`local-rag-ollama`](https://github.com/carlosgild-web/local-rag-ollama): fully local RAG
  with Ollama, with cited answers over versioned documents.
- [`luna-hybrid-agent`](https://github.com/carlosgild-web/luna-hybrid-agent): a local-first
  agent that picks between document search, read-only business SQL and an FX API.
- [`hl-create-design`](https://github.com/carlosgild-web/hl-create-design): an AI-assisted
  KiCad project generator with the company title block; the AI guides, the code decides.

## License

MIT. See [`LICENSE`](LICENSE). Fonts are open-license (OFL) and the logo is original.
