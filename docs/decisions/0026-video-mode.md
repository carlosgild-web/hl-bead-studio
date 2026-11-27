# 0026: `start.cmd video`: every take on fresh seed data in `data-video/`

**Status:** accepted (2026-11-26). Phase 10, as in hl-create-design's video mode.

## Context

The explainer video records the real app with a real model. A take must not show the SKUs,
designs and renders of earlier takes or of hand testing, and must never touch the designer's
own `data/`. Two takes in a row should reserve the same first SKU, so the storyboard and the
subtitles can name it. The catalog render takes about 90 s at the default 64 samples on this
PC, most of the wait in the video.

## Decision

1. **`start.cmd video [provider]`** (`./start.sh video [provider]`) sets `DATA_DIR` to
   `data-video/` and `DESIGNS_ROOT` to `data-video/designs/` for the mock SAP and the backend.
   Environment variables win over `.env`, so nothing else changes. The rest is the normal
   start: the free-ports check, then the model check and question, or the named provider.
2. **The reset is `demo-reset --yes`** (decision 0024) with those variables, run after the
   free-ports check so no SQLite file is open: the app database, the designs and the mock SAP
   database go, and the mock re-seeds its catalog from `sap-mock/seed/materials.json` at its
   start. No second reset path to keep in step. `data-video/` is gitignored; the model choice
   file goes there too in video mode.
3. **`RENDER_SAMPLES=16` in video mode**, unless the environment already sets it. Timed on
   GB-1034 in amber with Blender 5.2.3 (Cycles CPU, denoised): 64 samples 93 s, 32 samples
   55-56 s, 16 samples 37-49 s; most of the time is Blender's fixed start-up. At 1024 px the
   16-sample image is a little softer on the facets than the 64-sample one; at video size
   they look the same.

Checked: two rounds of reset, mock SAP start and a reservation both reserved GB-1034, and the
hashes of every file under `data/` were the same before and after. Tests:
`backend/tests/test_reset.py` (`test_video_mode_resets_data_video_and_leaves_data_alone`,
`test_the_first_video_start_has_nothing_to_reset`).

## Consequences

- The first SKU of every take is **GB-1034**, the same SKU as the gallery's showcase bead
  "Honey Glow Faceted" (decision 0024, item 5). The video's Renders tab must not mix the two;
  checked in the dry run (phase 10, step V5).
- Video renders are lighter than catalog renders; the README's gallery images stay at 64.
