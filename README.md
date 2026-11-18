# Bead Studio · Hilda & Luna Beadworks

[![CI](https://github.com/carlosgild-web/hl-bead-studio/actions/workflows/ci.yml/badge.svg)](https://github.com/carlosgild-web/hl-bead-studio/actions/workflows/ci.yml)

An AI-assisted internal tool for the Product Design team of the fictional company
**Hilda & Luna Beadworks**. A designer describes a glass bead or charm; the assistant proposes
parameters and explains the manufacturability rules from the Product Design Manual; after the
designer confirms, the tool reserves a SKU in a mock SAP, builds the 3D model (CadQuery: STEP,
STL, GLB), produces a technical drawing with the H&L title block and queues a catalog render
in Blender.

> **Status:** work in progress (Phase 4 of 9: geometry, drawings, validation and Blender
> catalog renders work from the command line; no AI or UI yet). The roadmap is in [`PLAN.md`](PLAN.md) and the design
> decisions in [`docs/decisions/`](docs/decisions/).

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
the CLI and, from Phase 5, by the designer's confirmation.

The [render gallery](docs/gallery/) for the online demo comes from the same pipeline:
`backend/.venv/Scripts/python scripts/build_gallery.py` (or `backend/.venv/bin/python` on
Linux and macOS) renders every design in `scripts/gallery.json` and writes small WebP images
and `manifest.json` (decision 0011).

Checks: `pytest -q && ruff check . && ruff format --check .` in each Python package, and
`npm run lint && npm test && npm run build` in `frontend/`.

## Related projects

- `luna-hybrid-agent`: the Hilda & Luna catalog, sales and inventory assistant.
- `hl-create-design`: machine-part design with KiCad and an AI guide.

## License

MIT. See [`LICENSE`](LICENSE).
