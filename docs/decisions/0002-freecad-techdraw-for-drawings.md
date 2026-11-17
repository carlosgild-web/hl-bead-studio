# 0002: FreeCAD TechDraw for the technical drawings

**Status:** accepted, pending the Phase 3 spike (2026-11-17)

## Context

Each design needs a technical drawing PDF with the Hilda & Luna title block (SKU, revision,
name, material, scale, date, drawn by) and the main views and dimensions, so the supplier and
the mold maker receive the same document every time.

## Decision

Use FreeCAD TechDraw headless: `freecadcmd` runs a script that imports the STEP, places front
and side views on an A4 page with the H&L SVG template (`cad/templates/hl_title_block_A4.svg`),
adds the key dimensions, fills the title block fields and exports a PDF.

The runner follows invariant 6: a subprocess with an argument list (no shell), a timeout,
captured stdout and stderr, and inputs passed as a JSON file rather than interpolated into code.

**Spike first (Phase 3).** TechDraw's PDF export has historically depended on the GUI. If the
headless export is not reliable, the fallback is CadQuery SVG projections placed into the same
SVG title block and rendered to PDF in Python. The spike result is recorded in a new decision.

## Consequences

- Drawings look like real engineering drawings and use a real CAD tool.
- FreeCAD is an optional dependency: tests that need it are marked `@pytest.mark.freecad` and
  skipped when `FREECAD_CMD` is missing, and CI does not need it.
- The online Docker image includes FreeCAD only if the spike passes (Phase 8).
