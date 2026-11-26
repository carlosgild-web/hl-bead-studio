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

## Findings (phase 10, steps V5-V6, 2026-11-26)

Five dry takes on demo mode (`start.cmd video fake`) before the first Groq take. Product code
was not changed; every fix is in the tooling or the storyboard.

| # | Finding | Kind | Fix |
|---|---|---|---|
| F1 | The panel checks a hand edit through `POST /api/preview` (validation and 3D preview together), not `/api/validate`: row 3.2 never matched | Tooling | The capture records `/api/preview` as `panel_check`; row 3.2 matches `validation.valid === false` |
| F2 | Demo mode never opens a reserve card from the chat: "Reserve a SKU for it as …" gets the Q&A bank's answer on how to reserve (the README GIF's card comes from the e2e server's scripted model) | Expected (decision 0022) | The dry run reserves with the panel's Reserve SKU… form (row 4.1d, dry run only); the Groq take asks in the chat (4.1, 4.2) |
| F3 | The panel's name field starts with a suggested first word; typing after it gave "AmberAmber Lantern", which GEN-03 refused live | Tooling | Clear the field first. The live GEN-03 check worked as designed |
| F4 | Demo mode does not call `preview_geometry`: row 2.4 never matches in a dry run | Expected | None; Groq may call it |
| F5 | A subtitle stayed on screen for 18-59 s: while the reserve form was typed, and while FreeCAD started and closed | Tooling | FreeCAD's start is a labelled wait; the take goes back to the app while FreeCAD closes; take cues end where the clip starts (`.srt`) |
| F6 | Row 6.1 fell inside a cut: the wait started at the click, before the confirm response | Tooling | The wait starts once the card shows "Render job #" |
| F7 | FreeCAD did not quit in time once: with Blender on every core a redraw took longer than a timer tick, so a fixed number of ticks ran long | Tooling | The turn follows the clock (`QElapsedTimer`); the time limit has more margin |
| F8 | The render took 78-144 s in a take against 37-49 s alone (Blender shares the CPU with FreeCAD, Edge and the recorder) | Expected | Cut to 1 s with its real length in the label |
| F9 | The title-block row was read after the zoom had ended | Tooling | The zoom starts first; the row is read while it is zoomed in |
| F10 | The first SKU of every take is GB-1034, the gallery's showcase bead (decision 0026) | No clash on screen | The gallery labels that bead "Showcase", not by SKU |
| F11 | Length: 3:29 at first, 2:47 after F5-F6 and a hold factor of 0.7 | Tooling | Generic rows for unforeseen tool calls capped at 3 (`VIDEO_MAX_GENERIC`); the others are listed in `take.json` |
| F12 | Groq takes (V6): the first asked for "Amber Lantern", which breaks GEN-03 (the panel adds "Faceted", the chat does not), and the model asked back instead of opening a card; the second ran 3:16 | Storyboard | The sentence names the full name; the published take uses a hold factor of 0.55 and one generic row (2:46) |
| F13 | In the published take the model wrote its arithmetic in LaTeX, which the chat shows as plain text; four subtitles read at 21-27 characters per second | Product (not changed); tooling | Math in the chat would be a product change. A hold now never goes under 17 characters per second |

Checked in every dry take: the payloads on screen equal the capture (10 of 10), no local path
in any payload, in the app's text or in FreeCAD's title, and `data/` untouched.

Every take reserves a new SKU and writes a design. In `start.cmd video` mode that happens in
`data-video/`, which the next start resets, so a take never shows the leftovers of an
earlier one. The end card shows the repo, `VIDEO_AUTHOR` and `VIDEO_LINKEDIN`.
