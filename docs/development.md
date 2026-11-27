# Development

The setup per service, the checks and the folders are in the README's
[Development](../README.md#development) section. This page has the rest: the launcher, the
command line, renders, the end-to-end tests and the stack.

## The launcher

`start.cmd` (Windows) and `./start.sh` (Linux and macOS) start the mock SAP (:8100), the
backend (:8000) and the UI, and open the browser. The first run sets up the virtual
environments and builds the UI.

```bash
start.cmd              # Windows: three windows, close them to stop
./start.sh             # Linux and macOS: Ctrl+C stops all three
start.cmd groq         # pick the LLM yourself: fake, ollama, anthropic, dahl or groq
start.cmd video        # fresh seed data in data-video/ for a video take (decision 0026)
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
`GROQ_API_KEY`), asks Ollama for its models, suggests the best one (the capital letter; Enter
accepts it) and starts the studio with your choice. A per-minute limit still counts as usable;
a Dahl model that is full (paid accounts go first) does not. Every question waits for you.
Without a terminal it asks nothing, takes the suggestion and never starts Ollama.
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

On Windows, `start.cmd` finds Blender in `Program Files` when `BLENDER_BIN` is not set.

## Back to the seed data

After a round of testing, `cd backend && python -m app.cli demo-reset` (servers stopped)
deletes the reserved test SKUs, generated designs, renders and conversations, and the mock
SAP starts again from its seed catalog (decision 0024).

## The generator without the UI

Validate a design and generate its files (STEP, STL, GLB, drawing PDF, `params.json`) under
`DESIGNS_ROOT` (default `data/designs/`):

```bash
cd backend
python -m app.cli validate --family FAC --params examples/fac_10mm.json
python -m app.cli generate --family FAC --params examples/fac_10mm.json \
  --sku GB-1034 --rev A --name "Honey Glow Faceted" --sap-material 50000134
```

Example drawings (PDF): [faceted bead](showcase/GB-1034_A_drawing.pdf) and
[crescent charm](showcase/CH-2034_A_drawing.pdf).

## Renders

Render a catalog image (1024 px PNG, Cycles on the CPU, in
`<DESIGNS_ROOT>/<SKU>/<Rev>/render/`) of a generated revision. This needs Blender 4.x or newer
(tested on 5.2) in `BLENDER_BIN`. The finish is any approved glass color for a bead or
plating for a charm, and defaults to the design's own:

```bash
python -m app.cli render --sku GB-1034 --rev A --finish ruby
```

The backend runs one render worker; Blender runs as a subprocess with a timeout
(`RENDER_TIMEOUT_S`), no shell and captured logs.

The [render gallery](gallery/) for the online demo comes from the same pipeline:
`backend/.venv/Scripts/python scripts/build_gallery.py` (or `backend/.venv/bin/python` on
Linux and macOS) renders every design in `scripts/gallery.json` and writes small WebP images
and `manifest.json` (decision 0011).

## The agent eval

```bash
cd backend
python -m app.cli agent-eval --fake                          # ideal scripts; must be 100% (CI)
python -m app.cli agent-eval --fake --suite all --variants   # + the qa suite on demo mode (CI)
python -m app.cli agent-eval --provider dahl --suite qa --out ../docs/eval
python -m app.cli agent-eval --provider groq --start-at <scenario id> --label run1-part2
python -m app.cli agent-eval --provider ollama --scenario hole-too-small-en
```

`--suite core` (the default) keeps real-provider runs comparable and within quota. Results and
what each run changed: [`docs/eval/`](eval/).

## End-to-end tests and README images

The end-to-end tests run the whole flow in Chromium on the FakeClient, with an in-memory SAP
and a stand-in for Blender (`scripts/e2e_server.py`):

```bash
cd e2e
npm ci && npx playwright install chromium
npx playwright test            # E2E_SCREENSHOTS=<folder> saves a screenshot per step
                               # E2E_API_PORT / E2E_UI_PORT move it off taken ports
npm run showcase               # the README's screenshots in docs/showcase/
npm run showcase:gif           # the README GIF (needs ffmpeg), on a fresh server
```

The README video has its own tooling in [`video/`](../video/README.md); how it was recorded
is in [video.md](video.md).

## Stack

| Layer | Choice |
|---|---|
| Geometry | CadQuery, one builder per family; GLB via trimesh |
| Drawing | OpenCascade hidden-line views + SVG title block → PDF (svglib, reportlab); decision 0009 |
| Render | Blender headless, Cycles CPU, SQLite job queue, one worker |
| LLM | Own `LLMClient` for Ollama, Anthropic and OpenAI-compatible APIs (Dahl, Groq), a demo client, a fake client for tests; a startup check and a fallback chain |
| Agent | Own bounded tool loop, no agent framework |
| Manual search | SQLite FTS5 over [`docs/manual/`](manual/) (Spanish and English) |
| Mock SAP | Separate FastAPI service, OData v2 payloads, basic auth + CSRF |
| Backend | Python 3.12+ (developed on 3.14, decision 0007), FastAPI, SQLAlchemy, pydantic-settings, httpx |
| Frontend | React, Vite, TypeScript, Tailwind, shadcn/ui, TanStack Query, react-three-fiber |
| Packaging | Docker (app + mock SAP); Blender only locally |
