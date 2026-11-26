# 0027: The README video: a real model under the hood, with a FreeCAD ending

**Status:** accepted (2026-11-26). Phase 10, steps V4-V7.

## Context

The portfolio's README standard asks for a 2¼-2¾ minute video of the real app with a real
model and an "Under the hood" panel, ending in the external tool that opens the generated
file. hl-create-design built that tooling (its decisions 0028, 0032 and 0036) and ends in
KiCad. Bead Studio's external tools are Blender (renders, already in the app) and a CAD
program for the STEP file; the product has no button that opens one.

## Decisions

1. **Port the tooling** from hl-create-design into `video/`: stage, conductor, capture by a
   wrapped `fetch`, flexible matching of storyboard rows to a real model's events, payloads
   only from the capture, `lines.mjs` callouts by file and symbol, `cues.mjs` checks,
   `compose.mjs`. `introspect.py` is rewritten over Bead Studio's own `ManualIndex`.
2. **Model: Groq `openai/gpt-oss-120b`**, as in hl-create-design (its decision 0032).
3. **FreeCAD instead of KiCad.** The recorder, not the product, opens the take's STEP file
   in FreeCAD 1.1 with a macro (`freecad_view.FCMacro`: Part workbench, isometric, shaded in
   the design's glass colour, one turn, quit without saving). There is no "Open in FreeCAD"
   button: that would be a product feature with its own phase and decision. FreeCAD runs as
   a bounded subprocess with an argument list, and the SKU and revision are checked before
   they become a path (invariants 4 and 6 hold in the tooling too).
4. **The render is queued before FreeCAD opens**, so the time FreeCAD is on screen is real
   Blender work, not a cut. What is left of the render (and FreeCAD's start) is cut to 1 s
   with its real length on screen.
5. **`desktop.mjs` generalizes `kicad.mjs`:** any window by process id, maximized, the
   title bar masked as well as the taskbar.
6. **Every wait the take records is labelled when it is cut**, not only the model's: the
   generation, FreeCAD's start, the end of the render (`waits.json`).
7. **A demo-mode dry run** (`npm run video:demo-dry`) rehearses the same steps with no model
   and no quota. Demo mode never opens a reserve card from the chat (decision 0022), so the
   dry run reserves with the panel's form.

## Consequences

- Recording needs Windows, Edge, ffmpeg, Blender and FreeCAD 1.1; tests and CI need none of
  them (`video/` has its own `npm run video:test` for the cutting logic).
- The published take is the third on Groq (2026-11-26): the first asked for a name that
  breaks GEN-03, and the model asked back instead of opening a card (the storyboard now
  names the full name); the second ran 3:16. The dry-run findings are in `video/README.md`.
- In the published take the model wrote LaTeX, which the chat shows as plain text. Rendering
  math in the chat would be a product change, not part of this phase.
