# Bead Studio · Hilda & Luna Beadworks

[![CI](https://github.com/carlosgild-web/hl-bead-studio/actions/workflows/ci.yml/badge.svg)](https://github.com/carlosgild-web/hl-bead-studio/actions/workflows/ci.yml)

An AI-assisted internal tool for the Product Design team of the fictional company
**Hilda & Luna Beadworks**. A designer describes a glass bead or charm; the assistant proposes
parameters and explains the manufacturability rules from the Product Design Manual; after the
designer confirms, the tool reserves a SKU in a mock SAP, builds the 3D model (CadQuery: STEP,
STL, GLB), produces a technical drawing with the H&L title block and queues a catalog render
in Blender.

> **Status:** work in progress (Phase 8 of 9). The studio works end to end, locally or in
> Docker: describe a product, review the proposed parameters with live validation, see the 3D
> model, and confirm the cards that reserve the SKU, generate the files and drawing, and
> queue the render. The assistant runs on Dahl, Groq, Ollama or Anthropic, and answers from a
> curated Q&A bank in demo mode; its evaluation runs are in [`docs/eval/`](docs/eval/). The
> roadmap is in [`PLAN.md`](PLAN.md) and the design decisions in
> [`docs/decisions/`](docs/decisions/).

## Principle: the AI guides, the code decides

The model turns a description into parameters, cites rule ids and drafts catalog text.
Whether a design can be made is decided by deterministic validators; reserving a SKU and
generating files happen only after the designer clicks **Confirm**.

## Quick start with Docker

Only Docker is needed. The studio, the mock SAP and the built UI run from one image
(decision 0018):

```bash
docker compose up --build        # then open http://localhost:8000
```

Without a key the assistant is in demo mode (the panel, the checks and the cards still
work). For the assistant, put a free Groq key in `.env` (`GROQ_API_KEY=...`, see
`.env.example`); `LLM_PROVIDER` defaults to `groq` in compose. When Groq's free daily quota
is used up, the studio uses a local Ollama model if one answers, else demo mode:

```bash
docker compose --profile ollama up -d
docker compose exec ollama ollama pull qwen3:4b-instruct-2507
# an Ollama already running on this machine instead: COMPOSE_OLLAMA_URL=http://host.docker.internal:11434
```

Renders need Blender, so they run in the local setup below; the Docker studio shows the
pre-generated gallery. Designs and the SQLite files live in the `studio-data` volume.

## Quick start (development)

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

Example drawings: [faceted bead](docs/showcase/GB-1034_A_drawing.pdf) and
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

## Related projects

- `luna-hybrid-agent`: the Hilda & Luna catalog, sales and inventory assistant.
- `hl-create-design`: machine-part design with KiCad and an AI guide.

## License

MIT. See [`LICENSE`](LICENSE).
