# 0003: Blender headless renders in a job queue

**Status:** accepted (2026-11-17)

## Context

The catalog needs a photo-like image of every new product in each finish (glass colors, gold
plate, rhodium, antique bronze). A Cycles render on a laptop CPU takes from tens of seconds to a
couple of minutes, far too long for an HTTP request.

## Decision

- `blender -b -P blender/render.py -- <job.json>` renders one image: it imports the GLB or STL,
  applies a material preset (glass with IOR 1.47 and the chosen color, or a metal), uses a
  studio light and a fixed camera, Cycles CPU with low samples and denoising, 1024 px PNG.
- Jobs live in a SQLite table (`queued`, `running`, `done`, `failed`) under `DATA_DIR`. A single
  in-process worker takes one job at a time (the same pattern as `luna-hybrid-agent`), and the
  UI follows the status over SSE.
- The subprocess follows invariant 6: argument list, timeout, captured logs, inputs in a JSON
  file.

## Consequences

- One worker keeps CPU use predictable on a laptop; no broker (Redis, Celery) to install.
- Blender is optional: tests that need it are marked `@pytest.mark.blender`; the online demo
  does not run renders (decision 0006).
- Queuing a render is a side effect, so it goes through the confirmation gate (decision 0005).
