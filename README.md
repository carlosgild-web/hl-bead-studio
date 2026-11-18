# Bead Studio · Hilda & Luna Beadworks

[![CI](https://github.com/carlosgild-web/hl-bead-studio/actions/workflows/ci.yml/badge.svg)](https://github.com/carlosgild-web/hl-bead-studio/actions/workflows/ci.yml)

An AI-assisted internal tool for the Product Design team of the fictional company
**Hilda & Luna Beadworks**. A designer describes a glass bead or charm; the assistant proposes
parameters and explains the manufacturability rules from the Product Design Manual; after the
designer confirms, the tool reserves a SKU in a mock SAP, builds the 3D model (CadQuery: STEP,
STL, GLB), produces a technical drawing with the H&L title block and queues a catalog render
in Blender.

> **Status:** work in progress (Phase 6 of 9). The studio UI works end to end: describe a
> product, review the proposed parameters with live validation, see the 3D model, and confirm
> the cards that reserve the SKU, generate the files and drawing, and queue the render. The
> roadmap is in [`PLAN.md`](PLAN.md) and the design decisions in
> [`docs/decisions/`](docs/decisions/).

## Principle: the AI guides, the code decides

The model turns a description into parameters, cites rule ids and drafts catalog text.
Whether a design can be made is decided by deterministic validators; reserving a SKU and
generating files happen only after the designer clicks **Confirm**.

## Quick start (development)

Requirements: Python 3.12+ (developed on 3.14), Node 22+.

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

- `fake` (the default) is demo mode and needs nothing.
- `ollama` runs locally (`OLLAMA_MODEL`, default `qwen3:4b-instruct-2507`).
- `anthropic` needs `ANTHROPIC_API_KEY`.

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
- **3D model** (right): the GLB built from the valid parameters, orbit controls, the glass
  color or plating finish, and the size, volume and mass.
- **Drawing** and **Renders** tabs: the PDF with the title block and the STEP, STL and GLB
  downloads; the render job followed live, and the pre-generated gallery.
- **Catalog**: the SAP materials, the SKUs reserved in Bead Studio and their drawings.
- ES/EN switch and a "How this demo works" guide.

The UI reads these routes, none of which has a side effect: `GET /api/families[/{code}]`,
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
```

## Related projects

- `luna-hybrid-agent`: the Hilda & Luna catalog, sales and inventory assistant.
- `hl-create-design`: machine-part design with KiCad and an AI guide.

## License

MIT. See [`LICENSE`](LICENSE).
