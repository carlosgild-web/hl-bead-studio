# 0011: Phase 4 render choices

**Status:** accepted (2026-11-17). Details of decision 0003, plus some small deviations from
`PLAN.md`.

## Context

Phase 4 turned decision 0003 into code: `blender/render.py`, the render queue and its worker
(`backend/app/render/`), read-only routes and the gallery script. Building the studio scene
and timing it on the development laptop (Blender 5.2.3, Cycles on an 8-thread CPU) led to the
choices below.

## Decisions

1. **The backend decides, Blender applies.** `render/presets.py` turns the content files into
   numbers: linear RGB from the approved hex colors, transmission, roughness, IOR 1.47 for
   borosilicate, and metal values from `finishes.json`. It also sets the framing for each kind
   of product. `blender/render.py` reads only a JSON job file and makes no product decisions.
   It runs with `--factory-startup --disable-autoexec --python-exit-code 1`, so a Python error
   in the script becomes a failed exit status (invariant 6).
   It works on Blender 4 and 5: `use_nodes`, deprecated in Blender 5 and removed in 6.0, is
   set only on Blender 4 (Blender 5 gives new materials and worlds a node tree).
2. **The GLB is the input.** It is the same file the web viewer shows, and it carries one
   normal per CAD face, so smooth shading rounds the curved faces and keeps every CAD edge
   sharp. The STL is not used.
3. **Normalized studio.** The model is scaled so that its largest dimension is one unit, and
   the lights, backdrop and camera never need tuning per product. The catalog shows shape and
   finish; the drawing carries the dimensions. Beads keep the hole upright and are seen from
   25° above, so the hole shows. Charms stand up facing the camera.
4. **Glass without caustics.** Refractive caustics are switched off, because low sample
   counts cannot resolve them. Shadow rays see the glass as tinted transparency instead, so a
   clear bead casts a light, colored shadow, not a black one. There is no volume absorption:
   the color comes from the Principled BSDF's transmission tint.
5. **Metals need a dark surround.** Polished plating reflects whatever is in front of it. A
   light world and floor made rhodium almost invisible on the light backdrop. The world is dim
   (the camera never sees it). The floor fades to dark beyond the edge of the frame, so flat
   faces show a soft light-to-dark gradient. Metals use fewer light bounces than glass.
6. **One still per job.** The camera sits on a turntable rig (an empty at the product's centre,
   turned by `azimuth_deg`), but each job renders one 1024 px still at a fixed ¾ angle. A
   turntable animation is not part of v1.
7. **A render may be replaced.** Design files are never overwritten (manual 08), but a render
   is derived from the design and the studio scene. Rendering the same finish again replaces
   the PNG (it is written in a work folder and moved into place), and the audit log keeps
   every run.
8. **Any approved finish.** A glass bead can be rendered in any approved color (GB-07) and a
   charm in any plating (CH-05), so the catalog can show the variants it offers. The default
   is the design's own color or finish. A finish of the wrong kind is refused with the rule
   id.
9. **Queue details.** Jobs are claimed with a conditional `UPDATE`, so the worker and a CLI run
   never render the same job. Jobs left `running` by a stopped server are marked failed at
   start-up and not retried: a job that crashed the server would crash it again. The audit
   log gets `render.queued`, `render.done` and `render.failed`.
10. **No route queues a render yet.** Phase 4 adds only `GET` routes (status, server-sent
    events, image, renders of a design). Queuing arrives with `POST /actions/{id}/confirm` in
    Phase 5 (invariant 2). A test fails if a render route accepts anything but `GET`. The
    event stream is a plain `StreamingResponse` that reads the job every 0.5 s; no new
    dependency.
11. **Gallery as WebP.** `scripts/build_gallery.py` generates the designs in
    `scripts/gallery.json` under `<DATA_DIR>/gallery-build/` and renders them with the same
    queue. It writes 800 px WebP images (3–9 KB each) and a `manifest.json` to
    `docs/gallery/`. Pillow, already installed with reportlab, is now listed in
    `requirements.txt`.
12. **New settings:** `RENDER_SAMPLES` (default 64) and `RENDER_TIMEOUT_S` (default 600).

## Timing

Measured on the development laptop (8 threads, 7.2 GB RAM) while building the gallery with
the final scene: 1024 px, 64 samples, including about 15 s of Blender start-up and import.

| Products | Renders | Time per render |
|---|---|---|
| Glass beads (RND, FAC, LEN, RON) | 6 | 51–66 s |
| Charms (CRS, INI, DSC) | 5 | 49–50 s |

All are under the "about 2 minutes" target. A local model served by Ollama at the same time
roughly doubles the time (107–126 s on an earlier version of the scene), because both use the
CPU. One Blender render peaks at about 1.4 GB of memory, so on this laptop other large apps
have to be closed first.

## Consequences

- Tests replace Blender with `tests/fake_blender.py` (success, error, timeout, no image), so CI
  needs no Blender. `tests/test_blender.py` (marker `blender`) renders a bead and a charm at
  128 px when `BLENDER_BIN` is set.
- The gallery must be rebuilt after a change to the scene or the materials.
