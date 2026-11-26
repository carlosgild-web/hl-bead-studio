# The README video

Records "a real model, under the hood" from the running app (decision 0027, tooling ported
from hl-create-design). [docs/video.md](../docs/video.md) says what it shows. Recording
needs Windows (Edge, and ffmpeg `gdigrab` for the FreeCAD window), ffmpeg on the `PATH`,
Blender for the render and FreeCAD 1.1 for the ending.

```bash
cd video && npm ci          # @playwright/test only; uses the installed Edge
npm run video:check         # every [file, symbol] in storyboard-groq.json still resolves
npm run video:test          # how compose.mjs cuts a take
npm run video:smoke         # ~14 s: the 1920x1080 stage -> out/smoke/
```

## Record it

1. Start the app on fresh seed data: `start.cmd video` (it resets `data-video/` and renders
   with 16 samples, decision 0026; your `data/` is not touched). Answer `n` to Dahl and `Y`
   to Groq, or run `start.cmd video groq`. Groq's free tier has a daily quota: one take uses
   three chat turns.
2. `VIDEO_DESIGN_NAME="Amber Lantern" npm run video:groq`. Use a name that is not in the SAP
   seed; the app adds "Faceted". It writes to `out/groq/`:
   - `take.webm`, the stage as recorded, and `freecad.mp4`, the FreeCAD window;
   - `video.mp4`, with every wait over 3 s shortened to 1 s and labelled with what it was
     and how long it took (the model, the generation, the rest of the render);
   - `video-readme.mp4` (1280x720, under 10 MB), `poster.png` and `subtitles.en.srt`;
   - `take.json`, with the models the runs used and the storyboard rows the model's turns
     never matched; `events.json`, `shown.json`, `waits.json`, `trace-turn-N.json`.
3. Leave the screen alone while FreeCAD is open (~25 s): it is recorded from the desktop.

`npm run video:demo-dry` records the same steps on demo mode (`start.cmd video fake`), into
`out/demo-dry/`, with no model and no quota: the dry run before a Groq take.
`npm run video:verify` re-checks a Groq take: rows, payloads against the capture, no paths.

## The FreeCAD ending

After the third click queues the render, `freecad.mjs` starts FreeCAD 1.1 with the take's
STEP file and `freecad_view.FCMacro`: Part workbench, isometric, fitted, shaded in the
design's glass colour (from `/api/families`), one slow turn, then FreeCAD quits without
saving. `desktop.mjs` records the window (maximized, title bar and taskbar masked) and
`compose.mjs` puts the clip where it ran, with the subtitles from `cues-freecad.json`. The
product has no "Open in FreeCAD" button; the recorder opens it. FreeCAD's GUI is found from
`FREECAD_GUI`, next to `FREECAD_CMD`, or in the standard install folders.
`node freecad.mjs GB-1034 A` opens a generated design in `data-video/` for a quick look.

## Files

| File | Role |
|---|---|
| `storyboard-groq.json` | The rows: trigger, subtitle, callouts, payload source; flexible mode (a real model's steps vary) |
| `record.spec.ts` | The take: guard, capture, conductor, scenes (`@smoke`, `@demo-dry`, `@groq`) |
| `stage.html`, `stage.js` | App iframe, "Under the hood" panel, subtitles, slides |
| `lines.mjs` | `file:symbol` → current line and excerpt (copied from hl-create-design) |
| `introspect.py` | FTS5 terms and BM25 ranking from the backend's own manual index (read only, backend venv) |
| `desktop.mjs` | Desktop capture of a window by process: maximize, mask the title bar, ffmpeg `gdigrab` |
| `freecad.mjs`, `freecad_view.FCMacro` | The FreeCAD ending: open the STEP, show it, turn it, quit |
| `cues-freecad.json` | The FreeCAD clip's label and subtitles |
| `cues.mjs`, `compose.mjs` | Cues, checks, wait cuts, `.mp4`, `.srt`, the README copy (ffmpeg) |
| `compose.test.mjs` | `npm run video:test` |

Every take reserves a new SKU and writes a design. In `start.cmd video` mode that happens in
`data-video/`, which the next start resets, so a take never shows the leftovers of an
earlier one. The end card shows the repo, `VIDEO_AUTHOR` and `VIDEO_LINKEDIN`.
