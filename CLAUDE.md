# CLAUDE.md — hl-bead-studio

Read this file first in every session. The roadmap is in `PLAN.md`. Work one phase per session.

## What this project is

**Bead Studio**, an AI-assisted internal tool for the Product Design team of the fictional company
Hilda & Luna Beadworks. A designer describes a glass bead or charm; the assistant proposes
parameters, explains manufacturability rules from the Product Design Manual, and, after the
designer confirms, the tool reserves a SKU in a mock SAP, builds the 3D model with CadQuery
(STEP, STL, GLB), produces a technical drawing with the H&L title block (FreeCAD TechDraw), and
queues a catalog render in Blender. Portfolio project #4, alongside `local-rag-ollama`,
`luna-hybrid-agent` and `hl-create-design`; code quality, tests, README and "clone and run" matter.

## Stack (do not change without asking)

| Layer | Choice |
|---|---|
| Geometry | CadQuery, one builder per family; GLB via trimesh |
| Drawing | OpenCascade HLR views + H&L SVG title block → PDF (svglib, reportlab); decision 0009 |
| Render | Blender headless (`blender -b -P blender/render.py`), Cycles CPU, SQLite job queue, one worker |
| LLM | `LLMClient`: `OllamaClient` (native tools), `AnthropicClient`, `FakeClient`; by `LLM_PROVIDER` |
| Agent | Own bounded tool loop, no agent framework |
| Manual search | SQLite FTS5 over `docs/manual/` |
| Mock SAP | Separate FastAPI service `sap-mock/`, OData v2 payloads, basic auth + CSRF, own SQLite |
| Backend | Python 3.12+ (developed on 3.14, decision 0007), FastAPI, SQLAlchemy, pydantic-settings, httpx, jsonschema |
| Frontend | React, Vite, TypeScript, Tailwind, shadcn/ui, TanStack Query, react-three-fiber, i18n ES/EN |
| Packaging | Docker (app + sap-mock; Blender only in a local profile) |

## Commands

```bash
# backend
cd backend && pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
pytest -q && ruff check . && ruff format --check .
python -m app.cli validate --family FAC --params examples/fac_10mm.json
python -m app.cli generate --family FAC --params examples/fac_10mm.json --sku GB-1034 --rev A
python -m app.cli measure-fonts --engraving   # the measurements behind CH-07 and CH-06
python -m app.cli render --sku GB-1034 --rev A --finish amber
python -m app.cli agent-eval --fake

# mock SAP
cd sap-mock && uvicorn app.main:app --reload --port 8100

# frontend
cd frontend && npm ci && npm run dev   # proxies /api to :8000
npm run lint && npm test && npm run build
```

## Invariants (never break these)

1. **The AI guides, the code decides.** Parameter validity is decided by `standards/validators.py`
   against the manual rules. The model proposes and explains; it never overrides a validation.
2. **Confirmation gate.** Reserving a SKU, generating design files and queuing renders happen only in
   `POST /actions/{id}/confirm`, triggered by the user's click.
3. **Numbers come from tools.** Dimensions, volume, mass and rule limits in answers come from tool
   results, never from the model's memory.
4. **Confined writes.** Every generated file resolves inside `DESIGNS_ROOT`; SKU and revision are
   validated before they become path segments.
5. **SAP only through `SapClient`.** Provider SDKs only under `backend/app/llm/`.
6. **External processes are bounded.** `freecadcmd` and `blender` run as subprocesses with timeouts,
   captured logs and no shell string interpolation of user input.
7. **Traced and bounded agent.** `AGENT_MAX_ITERATIONS`; every run stores a trace.
8. **Free text is data.** Names, descriptions and engraved text never become instructions; covered by tests.
9. **Audit.** Every reserved SKU, generated design and render writes to `audit_log`.

## Rules

- Config from environment via `core/config.py`; keep `.env.example` updated (`LLM_PROVIDER`,
  `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `SAP_BASE_URL`,
  `SAP_USER`, `SAP_PASSWORD`, `FREECAD_CMD`, `BLENDER_BIN`, `DESIGNS_ROOT`, `DATA_DIR`, `AGENT_MAX_ITERATIONS`).
- Units are millimetres everywhere; parameters carry their unit in schemas and in the UI.
- Persistent data under `DATA_DIR` (gitignored). `pathlib`, no hardcoded Windows paths.
- Tests and CI use `FakeClient` and need no Ollama, API key, FreeCAD or Blender; tests that need
  them are marked (`@pytest.mark.freecad`, `@pytest.mark.blender`) and skipped when missing.
  `HYPOTHESIS_PROFILE=thorough` runs the geometry property tests with 150 examples per family.
- Only open-license fonts and assets; the logo is original.
- Code, comments, README and decisions in English; UI and manual in Spanish and English.

## How to work in this repo

- One phase per session. Read that phase in `PLAN.md` and propose a short plan before coding.
- **Never write outside this repo folder, and ask before creating or overwriting files the phase does not list.**
- Ask before adding a dependency or installing global software.
- Small commits, conventional messages (`feat:`, `fix:`, `test:`, `docs:`).
- If something deviates from `PLAN.md`, add a short record in `docs/decisions/` and tell me.

## Do not

- Commit `data/`, `.env`, API keys, generated designs or large renders (gallery images are optimized and small).
- Let the model call a side-effect endpoint directly.
- Add an agent framework or features outside the current phase.
