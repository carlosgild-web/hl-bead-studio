# Bead Studio · Hilda & Luna Beadworks

[![CI](https://github.com/carlosgild-web/hl-bead-studio/actions/workflows/ci.yml/badge.svg)](https://github.com/carlosgild-web/hl-bead-studio/actions/workflows/ci.yml)

An AI-assisted internal tool for the Product Design team of the fictional company
**Hilda & Luna Beadworks**. A designer describes a glass bead or charm; the assistant proposes
parameters and explains the manufacturability rules from the Product Design Manual; after the
designer confirms, the tool reserves a SKU in a mock SAP, builds the 3D model (CadQuery: STEP,
STL, GLB), produces a technical drawing with the H&L title block and queues a catalog render
in Blender.

> **Status:** work in progress (Phase 0, skeleton). The roadmap is in [`PLAN.md`](PLAN.md) and
> the design decisions in [`docs/decisions/`](docs/decisions/).

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

Checks: `pytest -q && ruff check . && ruff format --check .` in each Python package, and
`npm run lint && npm test && npm run build` in `frontend/`.

## Related projects

- `luna-hybrid-agent`: the Hilda & Luna catalog, sales and inventory assistant.
- `hl-create-design`: machine-part design with KiCad and an AI guide.

## License

MIT. See [`LICENSE`](LICENSE).
