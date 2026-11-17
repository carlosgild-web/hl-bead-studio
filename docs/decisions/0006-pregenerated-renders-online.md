# 0006: Pre-generated renders for the online demo

**Status:** accepted (2026-11-17)

## Context

The public demo (Hugging Face Spaces, Phase 8) runs on a small shared CPU. Blender adds
hundreds of megabytes to the image, and a Cycles render there could take many minutes and
block other visitors.

## Decision

- The online image does **not** include Blender. Parameters, validation, the 3D viewer
  (three.js on the GLB) and the drawing work live.
- The render tab shows a gallery of renders made locally with the same pipeline
  (`docs/gallery/`, optimized PNG or WebP, small files) and says that renders run locally.
- Locally, `compose.yaml` has an optional Blender worker profile, and the CLI can render
  any design (`python -m app.cli render ...`).

## Consequences

- The online demo stays fast and cheap, and still shows real output of the render pipeline.
- The gallery has to be regenerated when the materials or the scene change (a script does it,
  Phase 4).
