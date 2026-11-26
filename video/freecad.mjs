/**
 * The FreeCAD ending (decision 0027): while Blender renders the catalog image, the take's
 * STEP file opens in FreeCAD on this PC, and desktop.mjs records the window. The product has
 * no "Open in FreeCAD" button (out of scope); the recorder starts FreeCAD itself.
 *
 * Invariant 6 holds here too: FreeCAD runs as a subprocess with a time limit, its arguments
 * are a list (no shell string), and the SKU, revision and colour are checked before they
 * become a path or reach the macro. The STEP path stays inside data-video/designs; it is
 * never shown (FreeCAD's title shows the label the macro sets, and the title bar is masked).
 *
 *   node freecad.mjs GB-1034 A '#c9822b'      open, turn, quit (no recording): a dry check
 */
import { spawn } from 'node:child_process'
import { existsSync, readdirSync } from 'node:fs'
import { dirname, join, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

import { captureWindow } from './desktop.mjs'

const HERE = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(HERE, '..')
export const MACRO = join(HERE, 'freecad_view.FCMacro')
const SKU_RE = /^(GB-1|CH-2)\d{3}$/
const REV_RE = /^[A-Z]{1,2}$/
const COLOR_RE = /^#[0-9a-fA-F]{6}$/

/** FreeCAD's GUI: FREECAD_GUI, else next to FREECAD_CMD, else the newest standard install. */
export function findFreecad(env = process.env) {
  if (env.FREECAD_GUI) return env.FREECAD_GUI
  const candidates = []
  if (env.FREECAD_CMD) candidates.push(join(dirname(env.FREECAD_CMD), 'freecad.exe'))
  for (const base of [env.LOCALAPPDATA && join(env.LOCALAPPDATA, 'Programs'), env.ProgramFiles].filter(Boolean)) {
    if (!existsSync(base)) continue
    const installs = readdirSync(base).filter((d) => /^FreeCAD \d/.test(d)).sort().reverse()
    candidates.push(...installs.map((d) => join(base, d, 'bin', 'freecad.exe')))
  }
  const found = candidates.find((p) => existsSync(p))
  if (!found) throw new Error('FreeCAD not found: set FREECAD_GUI to freecad.exe (FreeCAD 1.1)')
  return found
}

/** The take's STEP file: inside the video designs folder, from a checked SKU and revision. */
export function stepPath(sku, rev, designsRoot = process.env.VIDEO_DESIGNS_ROOT || join(ROOT, 'data-video', 'designs')) {
  if (!SKU_RE.test(sku) || !REV_RE.test(rev)) throw new Error(`not a SKU and revision: ${sku} ${rev}`)
  const root = resolve(designsRoot)
  const path = resolve(root, sku, rev, `${sku}_${rev}.step`)
  if (relative(root, path).startsWith('..') || !path.startsWith(root + sep)) throw new Error('STEP path outside the designs folder')
  if (!existsSync(path)) throw new Error(`no STEP file for ${sku} rev ${rev} in the video designs folder`)
  return path
}

/** Start FreeCAD on `step` with the view macro; the process quits by itself after the turn. */
export function openStep({ step, sku, rev, color, seconds, gui = findFreecad() }) {
  if (!COLOR_RE.test(color)) throw new Error(`not a colour: ${color}`)
  const child = spawn(gui, [step, MACRO], {
    env: { ...process.env, BEAD_VIEW_LABEL: `${sku} rev ${rev}`, BEAD_VIEW_COLOR: color, BEAD_VIEW_SECONDS: String(seconds) },
    stdio: 'ignore',
    windowsHide: false,
  })
  const exited = new Promise((resolveExit) => child.on('exit', (code) => resolveExit(code)))
  // Bounded: FreeCAD's start (~5-10 s), the hold and the turn, plus a margin.
  const limit = setTimeout(() => child.kill(), (seconds + 60) * 1000)
  exited.finally(() => clearTimeout(limit))
  return { child, exited }
}

/**
 * The clip: FreeCAD opens the take's STEP, desktop.mjs records `seconds` of the window,
 * then FreeCAD quits by itself. Writes freecad.mp4 and freecad.json in `outDir`.
 */
export async function captureFreecad({ sku, rev, color, outDir, now, seconds = 16 }) {
  const step = stepPath(sku, rev)
  // The turn runs a little longer than the recording, so the clip ends in motion.
  const { child, exited } = openStep({ step, sku, rev, color, seconds: seconds + 2 })
  try {
    const info = await captureWindow({
      pid: child.pid,
      clip: 'freecad',
      outDir,
      now,
      seconds,
      ready: new RegExp(`^\\W*${sku} rev ${rev} - FreeCAD`),
      name: 'FreeCAD',
    })
    const code = await exited
    if (code !== 0) throw new Error(`FreeCAD ended with code ${code}`)
    return info
  } catch (err) {
    child.kill()
    throw err
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [sku, rev, color = '#c9822b'] = process.argv.slice(2)
  const { exited } = openStep({ step: stepPath(sku, rev), sku, rev, color, seconds: 8 })
  exited.then((code) => {
    console.log(`FreeCAD ended with code ${code}`)
    process.exit(code === 0 ? 0 : 1)
  })
}
