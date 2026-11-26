import { spawnSync } from 'node:child_process'
import { mkdirSync, rmSync } from 'node:fs'
import { join } from 'node:path'

import { expect, type Page, test } from '@playwright/test'

/**
 * The README's images (Phase 9), on the same backend as the other tests (demo mode and the
 * scripted flow; no model, no SAP, no Blender): `npm run showcase` writes them to
 * docs/showcase/. Not part of `npm test` or CI (see playwright.config.ts). The GIF needs
 * ffmpeg on the PATH; without it the WebM video is kept and the GIF is skipped.
 */

const OUT = join('..', 'docs', 'showcase')
const SIZE = { width: 1280, height: 800 }

// Every test records (a worker-wide option); only the GIF test keeps its video.
test.use({ viewport: SIZE, video: { mode: 'on', size: SIZE } })

const answers = (page: Page) => page.locator('[data-role="assistant"]')

/** The portfolio banner stays out of the README images. */
async function open(page: Page) {
  await page.goto('/')
  await page.getByRole('button', { name: /Hide the guide|Ocultar la guía/ }).click()
}

async function shot(page: Page, name: string) {
  await page.screenshot({ path: join(OUT, `${name}.png`) })
}

/** WebM → GIF with a palette of its own, from `startS` seconds on; bounded at 120 s. */
function toGif(webm: string, gif: string, startS: number) {
  const filters =
    'fps=8,scale=800:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];' +
    '[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle'
  const run = spawnSync(
    'ffmpeg',
    ['-y', '-loglevel', 'error', '-ss', startS.toFixed(2), '-i', webm, '-vf', filters, '-loop', '0', gif],
    { timeout: 120_000, encoding: 'utf8' },
  )
  if (run.error || run.status !== 0) {
    console.warn(`showcase: no GIF (${run.error?.message ?? run.stderr.trim()}); the WebM stays at ${webm}`)
    return false
  }
  return true
}

test.describe('the GIF', () => {
  test('a description becomes a 3D model', async ({ page }) => {
    const t0 = Date.now()
    await open(page)
    await expect(page.getByRole('heading', { name: 'Bead Studio' })).toBeVisible()
    await page.waitForTimeout(800)
    const startS = (Date.now() - t0) / 1000 - 0.3

    const input = page.getByLabel('Describe the bead or charm…')
    await input.click()
    await input.pressSequentially('A 10 mm faceted amber bead', { delay: 55 })
    await page.waitForTimeout(400)
    await page.getByRole('button', { name: 'Send' }).click()
    const model = page.getByRole('img', { name: /3D model of the/ })
    await expect(model).toBeVisible()
    await expect(page.getByText(/Meets the Product Design Manual/)).toBeVisible()
    await page.waitForTimeout(2000)

    // A slow drag turns the bead in the viewer.
    const box = (await model.boundingBox())!
    const cx = box.x + box.width / 2
    const cy = box.y + box.height / 2
    await page.mouse.move(cx, cy)
    await page.mouse.down()
    for (let i = 1; i <= 30; i++) {
      await page.mouse.move(cx + i * 8, cy + Math.sin(i / 6) * 10)
      await page.waitForTimeout(40)
    }
    await page.mouse.up()
    await page.waitForTimeout(1500)

    const video = page.video()!
    await page.close()
    mkdirSync(OUT, { recursive: true })
    const webm = join(OUT, 'description-to-model.webm')
    await video.saveAs(webm)
    if (toGif(webm, join(OUT, 'description-to-model.gif'), Math.max(0, startS))) rmSync(webm)
  })
})

test('a confirmation card, then the workflow after Generate', async ({ page }) => {
  await open(page)
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
