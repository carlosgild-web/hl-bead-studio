# 0009: Technical drawings in Python (TechDraw spike result)

**Status:** accepted (2026-11-17). Closes the Phase 3 spike of decision 0002 and open
question 2 in `PLAN.md`; decision 0002 is superseded for the drawing pipeline.

## Context

Decision 0002 chose FreeCAD TechDraw run headless from `freecadcmd`, with a fallback if
headless PDF export was not reliable. The spike used FreeCAD 1.1.4 (winget, Windows 11):

| Attempt | Result |
|---|---|
| `freecadcmd` + `TechDraw` module | No PDF export in console mode: the module offers `writeDXFPage`, `viewPartAsSvg` and `projectToSVG`; `TechDrawGui` "cannot load Gui module in console application". |
| `freecad.exe` with `QT_QPA_PLATFORM=offscreen` and a macro calling `TechDrawGui.exportPageAsPdf` | First run: a blank page, then the process hung until killed (120 s timeout), with repeated "No valid GL context found". Second run, after opening the page view and pumping Qt events: the part and an extent dimension appeared, but the SVG template was not drawn and the 5:1 scale was ignored. |

Getting TechDraw to work would mean driving the GUI binary with event-loop workarounds,
on Windows and under Xvfb in Docker, for a result that depends on GUI timing. That is not
the bounded, reliable subprocess invariant 6 asks for.

## Decision

Use the fallback described in 0002:

- **Views:** OpenCascade hidden-line removal (`HLRBRep_Algo`, the same kernel TechDraw uses)
  on the exact CadQuery solid. First-angle projection: beads get a front view (hole axis
  vertical) with the top view below; charms a front view with the left side view to its
  right. Hidden edges are dashed.
- **Sheet:** `cad/templates/hl_title_block_A4.svg` (A4 landscape, H&L logo, the fields from
  manual section 08). Bead Studio places the views, draws the dimensions each family
  builder declares, chooses the largest scale of 10:1, 5:1, 2:1 and 1:1 that fits, and
  fills the fields with XML-escaped text (invariant 8).
- **PDF:** svglib + reportlab, pure Python (no native Cairo on Windows).
- **FreeCAD stays optional:** `FREECAD_CMD` is only used by the `@pytest.mark.freecad` tests
  that reopen each STEP in FreeCAD and compare validity and volume (Phase 3 "Done when").

## Consequences

- Drawings work in CI, in the tests and in the online demo with no external tool; a drawing
  takes about 0.1–0.6 s.
- New backend dependencies: `svglib` and `reportlab` (and CadQuery's own HLR).
- The drawings are simpler than TechDraw's (no automatic dimension layout or section
  views); each family builder lists its key dimensions explicitly.
- The Phase 8 Docker image does not need FreeCAD (about 1 GB less).
- `CLAUDE.md` (stack table) and `PLAN.md` are updated to say so.
