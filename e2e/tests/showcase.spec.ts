import { spawnSync } from 'node:child_process'
import { rmSync } from 'node:fs'
import { join } from 'node:path'

import { expect, type Page, test } from '@playwright/test'

/**
 * The README's images (Phase 9), on the same backend as the other tests (demo mode and the
 * scripted flow; no model, no SAP, no Blender): `npm run showcase` writes them to
 * docs/showcase/. Not part of `npm test` or CI (see playwright.config.ts). The GIF has its own
 * run (`npm run showcase:gif`) and needs ffmpeg on the PATH; without it the WebM is kept.
 */

const OUT = join('..', 'docs', 'showcase')
const SIZE = { width: 1280, height: 800 }

test.use({ viewport: SIZE })

const answers = (page: Page) => page.locator('[data-role="assistant"]')

/** The portfolio banner stays out of the README images. */
async function open(page: Page) {
  await page.goto('/')
  await page.getByRole('button', { name: /Hide the guide|Ocultar la guía/ }).click()
}

async function shot(page: Page, name: string) {
  await page.screenshot({ path: join(OUT, `${name}.png`) })
}

/**
 * WebM → GIF from `startS` to `endS` seconds, with the portfolio's README spec: 10 fps, 960 px wide,
 * a 96-colour palette of its own; bounded at 120 s.
 */
function toGif(webm: string, gif: string, startS: number, endS: number) {
  const filters =
    'fps=10,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];' +
    '[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle'
  const run = spawnSync(
    'ffmpeg',
    ['-y', '-loglevel', 'error', '-ss', startS.toFixed(2), '-to', endS.toFixed(2), '-i', webm, '-vf', filters, '-loop', '0', gif],
    { timeout: 120_000, encoding: 'utf8' },
  )
  if (run.error || run.status !== 0) {
    console.warn(`showcase: no GIF (${run.error?.message ?? run.stderr.trim()}); the WebM stays at ${webm}`)
    return false
  }
  return true
}

/**
 * The README GIF (phase 10): the whole flow on the e2e backend (scripted model, in-memory SAP),
 * with the real validators, CadQuery geometry and drawing. It reserves "Amber Glow Faceted",
 * which GEN-03 allows once per SAP, so it runs alone on a fresh server: `npm run showcase:gif`
 * (`npm run showcase` leaves it out). It launches Chromium's new headless mode itself: the
 * default headless shell has no PDF viewer, and the Drawing tab shows the drawing PDF.
 */
test('recorded demo for the README GIF @gif', async ({ playwright, baseURL }) => {
  test.setTimeout(180_000)
  const browser = await playwright.chromium.launch({ channel: 'chromium' })
  const context = await browser.newContext({ baseURL, viewport: SIZE, recordVideo: { dir: join(OUT, '.gif-video'), size: SIZE } })
  const page = await context.newPage()
  const t0 = Date.now()
  await open(page)
  await page.getByRole('button', { name: 'Demo guide' }).evaluate((el) => ((el as HTMLElement).style.display = 'none'))
  await expect(page.getByRole('heading', { name: 'Bead Studio' })).toBeVisible()
  await page.waitForTimeout(1000)
  const startS = (Date.now() - t0) / 1000 - 0.3

  // One sentence: the panel fills, the checks pass, a card waits for the click.
  const input = page.getByLabel('Describe the bead or charm…')
  await input.click()
  await input.pressSequentially('A 10 mm faceted amber bead for the Amber Hollow collection; reserve a SKU for it', {
    delay: 45,
  })
  await page.waitForTimeout(400)
  await page.getByRole('button', { name: 'Send' }).click()
  const model = page.getByRole('img', { name: /3D model of the/ })
  await expect(model).toBeVisible()
  await expect(page.getByText(/Meets the Product Design Manual/)).toBeVisible()
  await page.waitForTimeout(2000)

  // The reserve card: nothing reaches SAP until the click.
  const reserve = page.getByRole('article', { name: 'Reserve SKU in SAP' })
  const reserveConfirm = reserve.getByRole('button', { name: 'Confirm' })
  await reserveConfirm.scrollIntoViewIfNeeded()
  await reserveConfirm.hover()
  await page.waitForTimeout(700)
  await reserveConfirm.click()
  await expect(reserve).toContainText(/Reserved GB-\d{4}/)
  await page.waitForTimeout(1500)

  // Generate: review, confirm, the files.
  const review = page.getByRole('form', { name: 'Generate files…' }).getByRole('button', { name: 'Review & confirm' })
  await review.hover()
  await page.waitForTimeout(400)
  await review.click()
  const generate = page.getByRole('article', { name: 'Generate design files' })
  const generateConfirm = generate.getByRole('button', { name: 'Confirm' })
  await generateConfirm.scrollIntoViewIfNeeded()
  await generateConfirm.hover()
  await page.waitForTimeout(600)
  await generateConfirm.click()
  await expect(generate).toContainText(/Files written for GB-\d{4} rev A/, { timeout: 60_000 })
  await page.getByRole('form', { name: 'Render…' }).press('Escape')

  // No step waits now, so nothing is dimmed: a slow drag turns the amber bead.
  await model.scrollIntoViewIfNeeded()
  const box = (await model.boundingBox())!
  const cx = box.x + box.width / 2
  const cy = box.y + box.height / 2
  await page.mouse.move(cx, cy)
  await page.mouse.down()
  // Few steps: each move over the WebGL canvas takes a few hundred ms in this browser mode.
  for (let i = 1; i <= 10; i++) {
    await page.mouse.move(cx + i * 22, cy + Math.sin(i / 2) * 10)
  }
  await page.mouse.up()
  await page.waitForTimeout(200)

  // The drawing with the H&L title block, then a zoom on the title block.
  await page.getByRole('tab', { name: /Drawing/ }).click()
  const drawing = page.locator('iframe[title]').first()
  await drawing.scrollIntoViewIfNeeded()
  await page.waitForTimeout(4500) // the PDF viewer takes 1-3 s to draw, then a hold on the whole sheet
  await drawing.evaluate((el) => {
    const frame = el as HTMLIFrameElement
    frame.parentElement!.style.overflow = 'hidden'
    frame.style.transition = 'transform 1.2s ease-in-out'
    frame.style.transformOrigin = '100% 100%'
    frame.style.transform = 'scale(2.2)'
  })
  await page.waitForTimeout(3500)

  // The Renders tab: the gallery of real Blender renders.
  await page.getByRole('tab', { name: /Renders/ }).click()
  const gallery = page.getByRole('heading', { name: /gallery/i })
  await gallery.scrollIntoViewIfNeeded()
  await page.waitForTimeout(2500)
  const endS = (Date.now() - t0) / 1000

  const video = page.video()!
  await context.close()
  const webm = join(OUT, 'demo.webm')
  await video.saveAs(webm)
  await browser.close()
  rmSync(join(OUT, '.gif-video'), { recursive: true, force: true })
  if (toGif(webm, join(OUT, 'demo.gif'), Math.max(0, startS), endS)) rmSync(webm)
})

/**
 * The confirm card, the workflow, then the 3D viewer, the Drawing tab and the Renders tab of the
 * same design. Chromium's new headless mode, as in the GIF test, so the drawing PDF is drawn.
 */
test('a confirmation card, the workflow after Generate, then the model, drawing and renders', async ({
  playwright,
  baseURL,
}) => {
  test.setTimeout(120_000)
  const browser = await playwright.chromium.launch({ channel: 'chromium' })
  const page = await browser.newPage({ baseURL, viewport: SIZE })
  await open(page)
  await page.getByRole('button', { name: 'Demo guide' }).evaluate((el) => ((el as HTMLElement).style.display = 'none'))
  await page
    .getByLabel('Describe the bead or charm…')
    .fill('A 10 mm faceted amber bead for the Amber Hollow collection; reserve a SKU for it')
  await page.getByRole('button', { name: 'Send' }).click()
  const reserve = page.getByRole('article', { name: 'Reserve SKU in SAP' })
  await expect(reserve).toContainText('Amber Glow Faceted')
  await expect(page.getByRole('img', { name: /3D model of the/ })).toBeVisible()
  await page.waitForTimeout(2000)
  await shot(page, 'confirm-card')

  await reserve.getByRole('button', { name: 'Confirm' }).click()
  await expect(reserve).toContainText(/Reserved GB-\d{4}/)
  const sku = (await reserve.getByText(/Reserved GB-\d{4}/).textContent())!.match(/GB-\d{4}/)![0]
  const generateStep = page.getByRole('form', { name: 'Generate files…' })
  await generateStep.getByRole('button', { name: 'Review & confirm' }).click()
  const generate = page.getByRole('article', { name: 'Generate design files' })
  await generate.getByRole('button', { name: 'Confirm' }).click()
  await expect(generate).toContainText(`Files written for ${sku} rev A`, { timeout: 60_000 })
  // The Render step opens and waits; Esc sets it aside to show the workflow with two steps done.
  await page.getByRole('form', { name: 'Render…' }).press('Escape')
  await page.getByText('Workflow', { exact: true }).scrollIntoViewIfNeeded()
  await page.waitForTimeout(1500)
  await shot(page, 'workflow')

  await page.getByRole('img', { name: /3D model of the/ }).scrollIntoViewIfNeeded()
  await page.waitForTimeout(1500)
  await shot(page, 'viewer-3d')

  await page.getByRole('tab', { name: /Drawing/ }).click()
  await page.locator('iframe[title]').first().scrollIntoViewIfNeeded()
  await page.waitForTimeout(4500) // the PDF viewer takes 1-3 s to draw
  await shot(page, 'drawing-tab')

  await page.getByRole('tab', { name: /Renders/ }).click()
  await page.getByRole('heading', { name: /gallery/i }).scrollIntoViewIfNeeded()
  await page.waitForTimeout(2500)
  await shot(page, 'renders-tab')
  await browser.close()
})

test('the studio in Spanish', async ({ page }) => {
  await open(page)
  await page.getByRole('button', { name: 'Español' }).click()
  await page.getByLabel('Describe la cuenta o el dije…').fill('Una cuenta facetada de 10 mm en ámbar')
  await page.getByRole('button', { name: 'Enviar' }).click()
  await expect(answers(page).last()).not.toBeEmpty()
  await expect(page.getByRole('img', { name: /^Modelo 3D de/ })).toBeVisible()
  await page.waitForTimeout(2000)
  await shot(page, 'studio-es')
})
