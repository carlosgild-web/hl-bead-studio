# PLAN.md — hl-bead-studio

Portfolio project #4. Roadmap for building **Bead Studio**, an AI-assisted internal tool that
the Product Design team of the fictional company **Hilda & Luna Beadworks** uses to design new
glass beads and charms: from a conversation to a validated 3D model, a technical drawing with
the company title block, and a catalog render.

Read `CLAUDE.md` first. One phase per Claude Code session. A phase is done only when its
**Done when** list passes and `ruff`, `pytest`, `npm run lint` and `npm test` are green.

---

## 1. The story (what the demo shows)

Hilda & Luna Beadworks sells glass beads (`GB-10xx`) and charms (`CH-20xx`). The catalog, sales
and inventory already exist in `luna-hybrid-agent` (CH-2004 "Crescent Moon & Star" is the best
seller; glass is borosilicate from Cristal Dorado Vidrios). Machines are designed in
`hl-create-design`. This repo designs **the product itself**.

**The problem.** A new bead goes from a sketch to the supplier and the mold maker through emails
and spreadsheets. Dimensions that cannot be made (a hole too small for the mandrel, a charm loop
too thin to survive plating) are found late. Every drawing has a different title block, and the
SKU and SAP material are typed by hand.

**The tool.** *Bead Studio* lets a designer:
1. describe the product in Spanish or English ("a 10 mm faceted bead, amber, for Amber Hollow");
2. review and adjust the parameters the assistant proposes;
3. get them validated against the Product Design Manual (manufacturability rules);
4. reserve a SKU and SAP material in the mock SAP;
5. generate the 3D model (STEP for manufacturing, STL, GLB for the web viewer);
6. generate the technical drawing PDF with the Hilda & Luna title block;
7. queue a Blender render for the catalog.

**The AI's role: a guide, not a decider** (same principle as hl-create-design). The assistant turns
a description into parameters, explains rule violations citing the manual, suggests a name that
follows the naming convention, and drafts the catalog description. Validity is decided by code;
reserving a SKU and generating files require the designer's confirmation in the UI.

---

## 2. Decisions taken (2026-11-17)

| Topic | Decision |
|---|---|
| Repo | New: `hl-bead-studio` (GitHub `carlosgild-web/hl-bead-studio`) |
| Scope | Product: glass beads and charms (not machine parts) |
| 3D model | **CadQuery** (Python, headless): parametric families → STEP, STL, GLB |
| Drawing | OpenCascade HLR views + H&L SVG title block → PDF in Python (decision 0009; TechDraw spike failed) |
| Render | **Blender** headless (`blender -b -P`), Cycles CPU, background job queue |
| Online demo | Live: parameters, validation, 3D viewer (three.js), drawing. Renders: pre-generated gallery |
| SAP | Own copy of a mock SAP (FastAPI, OData v2 shape) with a Material/SKU entity |
| LLM | `LLMClient`: Ollama (local) + Anthropic (cloud) + Fake (CI), by `LLM_PROVIDER` |
| UI | React + Vite + TypeScript + Tailwind + shadcn/ui + react-three-fiber |
| Roles | Creation only |

---

## 3. Company standards (fictional, to write in `docs/manual/{es,en}/`)

**Product families (v1)**

| Family | Code | Type | Main parameters |
|---|---|---|---|
| Round | `RND` | Glass bead | diameter, hole |
| Faceted | `FAC` | Glass bead | diameter, facet count (8–32), facet rows, hole |
| Lentil | `LEN` | Glass bead | diameter, thickness, hole |
| Rondelle | `RON` | Glass bead | diameter, height, hole |
| Crescent | `CRS` | Charm | height, crescent width, star (yes/no), thickness, loop |
| Initial | `INI` | Charm | letter A–Z, font (open-license), height, thickness, loop |
| Disc | `DSC` | Charm | diameter, thickness, engraved text or icon, loop |

**SKU:** glass beads `GB-1NNN`, charms `CH-2NNN` (sequence issued by SAP; existing catalog
GB-1001…GB-1033 and CH-2004…CH-2033 is seeded and never reissued).

**SAP material:** 18 digits with leading zeros, range `000000000050000000`–`000000000059999999`
(finished goods), shown without leading zeros.

**Design revision:** `A`, `B`, `C`… skipping `I, O, Q, S, X, Z`.

**Manufacturability rules (examples; the manual holds the full list with ids)**

| Id | Rule |
|---|---|
| `GB-01` | Hole 1.0–2.5 mm (mandrel sizes 1.0, 1.5, 2.0, 2.5) |
| `GB-02` | Glass wall around the hole ≥ 1.5 mm |
| `GB-03` | Diameter 4–20 mm; faceted beads ≥ 6 mm |
| `GB-04` | Lentil thickness ≥ 40% of diameter |
| `CH-01` | Charm thickness 1.0–3.0 mm |
| `CH-02` | Loop inner diameter ≥ 1.5 mm, loop wall ≥ 0.8 mm (survives plating and jump rings) |
| `CH-03` | Smallest feature (stroke, star point) ≥ 0.6 mm (mold limit) |
| `CH-04` | Height 8–30 mm |
| `CH-05` | Finishes: gold plate, rhodium, antique bronze; glass colors from the color list |

**Naming convention:** `<Evocative name> <Family>` in English, 2–4 words, unique in the catalog
(for example "Desert Sand Faceted"). Collections: Permanente, Coastal Garden, Amber Hollow.

**Files per design:** `<DESIGNS_ROOT>/<SKU>/<Rev>/` with `<SKU>_<Rev>.step`, `.stl`, `.glb`,
`<SKU>_<Rev>_drawing.pdf`, `render/<SKU>_<Rev>_<finish>.png`, `params.json`.

---

## 4. Architecture

```text
React UI (assistant chat + parameter panel + 3D viewer + drawing + render gallery)
        │  REST + SSE
        ▼
backend (FastAPI)
  ├─ agent/      bounded tool loop, trace, confirmation gate
  ├─ llm/        OllamaClient | AnthropicClient | FakeClient
  ├─ standards/  family schemas + manufacturability validators + manual search (SQLite FTS5)
  ├─ geometry/   CadQuery family builders → STEP / STL / GLB, mass and volume
  ├─ drawing/    OpenCascade HLR views + H&L SVG title block → PDF (decision 0009)
  ├─ render/     Blender job runner (blender -b -P scripts/render.py), job queue in SQLite
  ├─ sap/        SapClient ──HTTP──► sap-mock (FastAPI, OData v2)
  └─ db/         designs, jobs, audit_log, agent_runs
```

**Agent tools**

| Tool | Kind | Notes |
|---|---|---|
| `search_design_manual(query)` | read | FTS5, passages with rule ids |
| `list_families()` / `describe_family(code)` | read | Parameter schema, ranges, defaults |
| `validate_parameters(family, params)` | read | Deterministic; violations with rule ids and the nearest valid value |
| `preview_geometry(family, params)` | read | Builds the model in memory: volume, mass by material, bounding box, GLB for the viewer |
| `check_catalog(name)` | read | Name unique? Similar products (from the seeded catalog) |
| `sap_get_material(sku)` | read | Status and data of an existing SKU |
| `propose_parameters(family, params)` | UI | Fills the parameter panel; the user can edit |
| `request_reserve_sku(type, name)` | **gated** | Confirmation card; the click calls SAP |
| `request_generate_design(sku, rev, params)` | **gated** | STEP/STL/GLB + drawing PDF |
| `request_render(sku, rev, finish)` | **gated** | Queues a Blender job |
| `draft_catalog_text(sku)` | read | Drafts the catalog description from params and the brand tone |

**Mock SAP (sap-mock service)**

```text
GET  /sap/opu/odata/sap/ZHL_MM_MATERIAL_SRV/$metadata
GET  /sap/opu/odata/sap/ZHL_MM_MATERIAL_SRV/MaterialSet('CH-2004')?$format=json
GET  /sap/opu/odata/sap/ZHL_MM_MATERIAL_SRV/MaterialSet?$filter=MaterialType eq 'CHARM'
POST /sap/opu/odata/sap/ZHL_MM_MATERIAL_SRV/MaterialSet     (reserve SKU + material; x-csrf-token)
```
Basic auth, CSRF handshake, OData v2 payloads (`{"d": ...}`, `/Date(...)/`), SAP-style errors,
chaos switches (`SAP_LATENCY_MS`, `SAP_FAIL_RATE`, maintenance 503). Seeded with the 10 catalog
SKUs from luna-hybrid-agent plus ~15 fictional ones (statuses `IN_DESIGN`, `ACTIVE`, `DISCONTINUED`).

---

## 5. Repo layout

```text
hl-bead-studio/
  CLAUDE.md  PLAN.md  README.md  LICENSE  CHANGELOG.md  .env.example
  backend/app/{api,core,agent,llm,standards,geometry,drawing,render,sap,db}/  backend/tests/
  sap-mock/app/  sap-mock/tests/  sap-mock/seed/
  cad/templates/  (hl_title_block_A4.svg for TechDraw, materials and colors json)
  blender/  (scene.blend or scene built by script, render.py, materials: glass, gold, rhodium, bronze)
  frontend/src/{pages,components,api,hooks,i18n,viewer}/
  docs/manual/{es,en}/  docs/decisions/  docs/showcase/  docs/gallery/  (pre-generated renders)
  e2e/  scripts/  data/ (gitignored)
  compose.yaml  Dockerfile  start.cmd  start.sh  .github/workflows/
```

---

## 6. Phases

### Phase 0 — Skeleton and decisions
- `git init`, `.gitignore`, MIT license, `.env.example`, backend and sap-mock packages (pyproject,
  ruff, pytest), Vite React TS frontend with Tailwind, shadcn/ui, react-three-fiber.
- Decision records: 0001 CadQuery for geometry, 0002 FreeCAD TechDraw for drawings, 0003 Blender
  headless renders in a job queue, 0004 provider-agnostic LLM, 0005 confirmation gate, 0006 renders
  pre-generated for the online demo.
- CI: ruff + pytest + frontend lint/test/build.

**Done when:** CI green with one smoke test per package.

### Phase 1 — Company content
- Product Design Manual (section 3) in ES and EN, every rule with an id.
- Family schemas as JSON Schema (ranges, defaults, units in mm).
- Colors and finishes list (name, hex, Blender material preset).
- SAP seed: the 10 luna SKUs + fictional ones.
- Original H&L monogram logo (SVG) for the title block.

**Done when:** manual reviewed by Carlos; seeds and schemas validate.

### Phase 2 — Mock SAP service
- Endpoints from section 4, auth, CSRF, OData payloads, errors, chaos switches, `/health`.
- SKU reservation: next free number per type, atomic, never reuses a seeded SKU.
- Tests: lookup, filter, reserve, auth and CSRF failures, 404, 503.

**Done when:** `curl` examples in `sap-mock/README.md` work; tests green.

### Phase 3 — Geometry, drawing and validation (no AI yet)
- `standards/validators.py`: every manual rule, each violation with rule id and nearest valid value.
- `geometry/`: one CadQuery builder per family; export STEP, STL and GLB (via trimesh); compute
  volume and mass (borosilicate 2.23 g/cm³, zinc alloy 6.6 g/cm³).
- **Spike first (half a day):** FreeCAD TechDraw headless from `freecadcmd` (import STEP, front
  and side views, dimensions, title block template, export PDF). If headless export is not
  reliable, fallback: CadQuery SVG projections + the same SVG title block, rendered to PDF in Python.
  Record the result in a decision. *(Done: fallback, decision 0009.)*
- CLI: `python -m app.cli generate --family FAC --params params.json --sku GB-1034 --rev A`.
- Showcase files: drawing PDF of a new faceted bead and a crescent charm.

**Done when:** every family builds within its ranges (property-based test with random valid params),
invalid params fail with the right rule id, STEP opens in FreeCAD, drawing PDF has the filled title block.

### Phase 4 — Blender renders
- `blender/render.py`: import GLB or STL, apply material preset (glass with IOR 1.47 and color,
  gold plate, rhodium, antique bronze), studio light, turntable camera, Cycles CPU with low
  samples + denoise; 1024 px PNG.
- Job queue in SQLite with a single in-process worker (like luna); status over SSE.
- Script to build the gallery for the online demo (`docs/gallery/`).

**Done when:** a job renders a bead and a charm in under ~2 minutes on Carlos's laptop; the gallery is generated.

### Phase 5 — LLM layer and agent
- `llm/` clients (Ollama native tools with `qwen3:4b-instruct-2507`, Anthropic, Fake).
- Bounded loop, tool registry, trace, confirmation gate (`POST /actions/{id}/confirm`).
- Prompt: guide role, propose parameters as numbers with units, cite rule ids, never claim a file
  or SKU exists unless a tool result says so.
- Free text (names, descriptions, engraved text) is data: prompt-injection tests.

**Done when:** scripted conversations pass on Fake; manual runs work on Ollama and Anthropic.

### Phase 6 — React UI
- Layout: assistant chat (left), parameter panel with live validation (center), 3D viewer with
  orbit and finish switch (right); tabs for drawing PDF and renders.
- The assistant fills parameters (highlighted until touched), shows rule violations inline, shows
  SAP and confirmation cards, and the render job progress.
- Catalog view: existing SKUs and new designs.
- ES/EN, "How this demo works" banner with the `portfolio-demo-guide` skill, H&L brand colors.

**Done when:** flow description → parameters → validation → reserve SKU → model + drawing → render works; vitest + one Playwright e2e on Fake.

### Phase 7 — Evaluation and hardening
- ~25 scenarios: valid bead and charm, hole too small, loop too thin, out-of-range diameter,
  duplicate name, letter "I" revision, SAP down, Blender missing, prompt injection in engraved
  text, ES and EN, one-sentence spec.
- Score: correct parameters within tolerance, cited rule ids, no unconfirmed side effects.
- `agent-eval --fake` in CI; real runs on Ollama and Anthropic in `docs/eval/`.
- Online safety: rate limit, daily token cap, cleanup of generated files.

**Done when:** 100% on Fake; real-provider results published, failures included.

### Phase 8 — Packaging and online demo
- Docker image: Python + CadQuery + built frontend (no FreeCAD: decision 0009). Blender is
  **not** in the online image; the render tab shows the gallery and says renders run locally.
- `compose.yaml`: app + sap-mock (+ optional ollama, + optional blender worker profile for local use).
- `start.cmd` / `start.sh`; Hugging Face Spaces with `LLM_PROVIDER=anthropic`, Fake fallback without a key.

**Done when:** `docker compose up` works on a clean machine; public URL works.

### Phase 9 — Showcase
- README (English): problem, GIF (description → 3D model), drawing and render images, architecture,
  "AI as a guide" principles, eval table, try-it, decisions; links to luna-hybrid-agent and hl-create-design.
- Video 2–3 min, screenshots, release v1.0.0, CV and LinkedIn post.

**Done when:** README reviewed; release published.

---

## 7. Prerequisites (Windows)

| Tool | Notes |
|---|---|
| Python 3.12+ | CadQuery installs with pip; `cadquery-ocp` has a 3.14 wheel (decision 0007) |
| FreeCAD 1.x (optional) | `freecadcmd.exe` path in `FREECAD_CMD`; only for the tests that reopen STEP files |
| Blender 4.x or newer | `blender.exe` path in `BLENDER_BIN` |
| Node 20+ | frontend |
| Ollama | `qwen3:4b-instruct-2507` |
| Anthropic API key | cloud provider and online demo |
| Docker Desktop, `gh` | Phase 8 |

## 8. Open questions (decide before the phase that needs them)

1. ~~Phase 1: which open-license fonts for the Initial charm?~~ Decided: Pacifico, Cinzel Bold,
   Montserrat ExtraBold (OFL), decision 0008.
2. ~~Phase 3: result of the FreeCAD headless spike (TechDraw or fallback).~~ Decided: fallback,
   OpenCascade HLR views + SVG title block → PDF in Python, decision 0009.
3. Phase 5: an image input later ("make a charm like this sketch")? Not in v1.
4. Later: export a STEP package for the mold maker, cost estimate from mass and supplier prices
   (could reuse luna's supplier data), approval workflow.
