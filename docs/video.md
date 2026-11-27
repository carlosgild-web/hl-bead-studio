# The video

A 2¾-minute recording of the real app with a real model: Groq, `openai/gpt-oss-120b`
(decision 0027). On the left is the app. On the right, an "Under the hood" panel shows the
code behind each step and the data that passed through it. At the end, while Blender renders
the catalog image, the generated STEP file opens in FreeCAD, recorded on the desktop.

## What it shows

| Time | Step | What to notice |
|---|---|---|
| 0:00 | Title | |
| 0:08 | "Why are 32 facets per row too many for a 10 mm bead?" | The model calls `search_design_manual` with its own keywords. SQLite FTS5 ranks the manual's sections (BM25, headings weigh 3×); the panel shows the terms and the ranking, from `video/introspect.py`, and GB-05 comes first. |
| 0:25 | The answer | Written by the model from the passage: π × 10 / 32 ≈ 0.98 mm, under GB-05's 1.5 mm minimum. |
| 0:34 | "A 10 mm faceted amber bead for the Amber Hollow collection" | The model looks up the family, checks the catalog and validates, then `propose_parameters` fills the panel. The validators decide; amber marks the values the assistant proposed. |
| 0:57 | 32 facets per row, by hand | The panel's live check (`POST /api/preview`) answers with rule GB-05 and the nearest valid values. One click takes 20. |
| 1:17 | "Reserve a SKU for it as Amber Lantern Faceted" | The model can only open a card. Nothing reaches SAP until the designer clicks Confirm. |
| 1:38 | Confirm | `POST /api/actions/{id}/confirm` → `SapClient` → the mock SAP issues GB-1034 and material 50000134. |
| 1:51 | Generate | A second card and a second click. The rules are checked again; STEP, STL, GLB and the PDF drawing are written inside the designs folder only. |
| 2:06 | The drawing | A zoom on the H&L title block: SKU, revision, SAP material, scale and mass. |
| 2:15 | Render | A third click queues a Blender render (16 samples in video mode). |
| 2:20 | FreeCAD | The STEP file in FreeCAD 1.1, recorded on the desktop, while Blender works. |
| 2:38 | The render | The finished image, followed live over server-sent events. |
| 2:41 | End | |

## Is it real?

- **The app and the model are real.** It is the app as `start.cmd video` runs it (fresh
  seed data in `data-video/`, decision 0026), and every answer and tool call comes from the
  model. Rows that the model's steps did not match are left out and listed in the take's
  `take.json`. Tool calls the storyboard did not foresee get a generic row; this take shows
  one (`describe_family`) and lists the other five.
- **Every wait is labelled.** Waits over 3 s are cut to 1 s with a label that says what it
  was and how long it took. This take: two model waits (45 s and 39 s), the generation
  (9 s), FreeCAD's start (26 s) and the end of the render (42 s).
- **The panel shows captured data.** Each payload is the event, request or response the app
  received during the take. `cues.mjs` compares each one with the capture again (12 of 12),
  checks that the FTS ranking shown is the order the tool returned, and that no local path
  appears. The code excerpts are found by file and symbol (`lines.mjs`), so their line
  numbers are the current ones.
- **The files are real.** The drawing is the generated PDF; the zoom is a CSS scale of the
  app's own frame in the recording. FreeCAD opens the generated STEP file; the macro only
  sets the view and turns it, and FreeCAD quits without saving.

Known in this take: the model wrote its arithmetic in LaTeX (`\[ \frac{…} \]`), which the
chat shows as plain text; and four subtitles go by quickly (21-27 characters per second).
The recorder now holds a subtitle at least as long as it takes to read it at 17 per second.

## Record it again

See [video/README.md](../video/README.md). In short:

```bash
start.cmd video groq             # fresh seed data in data-video/, Groq
cd video && npm ci
VIDEO_MAX_GENERIC=1 VIDEO_DESIGN_NAME="Amber Lantern" npm run video:groq
```

The output in `video/out/groq/` is `video.mp4`, `video-readme.mp4` (1280x720, under 10 MB,
for the README), `poster.png` and `subtitles.en.srt`. `npm run video:demo-dry` rehearses the
same steps on demo mode, with no model. The tooling is described in decision 0027.
