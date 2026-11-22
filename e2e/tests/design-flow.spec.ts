import { join } from 'node:path'

import { expect, type Page, test } from '@playwright/test'

/** With E2E_SCREENSHOTS=<folder>, a full-page screenshot at each step (for the docs). */
async function snap(page: Page, name: string) {
  const folder = process.env.E2E_SCREENSHOTS
  if (folder) await page.screenshot({ path: join(folder, `${name}.png`), fullPage: true })
}

/**
 * Description → parameters → validation → reserve SKU → model + drawing → render, with every
 * side effect behind the designer's click on a confirmation card.
 */
test('a designer takes a faceted bead from a description to a render', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Bead Studio' })).toBeVisible()
  await expect(page.getByText(/LLM: fake/)).toBeVisible()

  // The demo guide: the drawer marks the first step, Escape closes it.
  await page.getByRole('button', { name: 'How this demo works' }).click()
  const drawer = page.getByRole('dialog')
  await expect(drawer.locator('[aria-current="step"]')).toContainText('Describe the product')
  await snap(page, '0-guide')
  await page.keyboard.press('Escape')
  await expect(drawer).toBeHidden()

  // 1. Description: the assistant proposes parameters, builds the preview, opens a card.
  const input = page.getByLabel('Describe the bead or charm…')
  await input.fill('A 10 mm faceted amber bead for the Amber Hollow collection; reserve a SKU for it')
  await page.getByRole('button', { name: 'Send' }).click()
  await expect(page.locator('[data-role="assistant"]').last()).toContainText('Confirm the card')

  // 2. Parameters: filled by the assistant and highlighted; valid by the code's check.
  const diameter = page.getByLabel('Diameter', { exact: false }).first()
  await expect(diameter).toHaveValue('10')
  await expect(page.locator('[data-proposed]').first()).toBeVisible()
  await expect(page.getByText(/Meets the Product Design Manual/)).toBeVisible()
  await expect(page.getByRole('img', { name: /3D model of the/ })).toBeVisible()
  await page.waitForTimeout(1500) // let the viewer draw
  await snap(page, '1-proposal')

  // 3. Validation: a value outside the manual is refused with a rule id; the nearest valid
  //    value fixes it.
  const facets = page.getByLabel('Facets', { exact: false }).first()
  await facets.fill('40')
  const violations = page.getByRole('alert', { name: 'Rule violations' })
  await expect(violations).toBeVisible()
  await expect(violations.getByText(/^GB-\d+$/).first()).toBeVisible()
  await violations.getByRole('button', { name: /facet_count = 32/ }).click()
  await expect(facets).toHaveValue('32')
  // 32 facets fit the range but are too narrow on a 10 mm bead (GB-05): the next suggestion.
  await expect(violations.getByText('GB-05')).toBeVisible()
  await snap(page, '2-violation')
  await violations.getByRole('button', { name: /facet_count = 20/ }).click()
  await expect(facets).toHaveValue('20')
  await expect(page.getByText(/Meets the Product Design Manual/)).toBeVisible()

  // 4. Reserve the SKU: nothing happens until Confirm.
  const reserve = page.getByRole('article', { name: 'Reserve SKU in SAP' })
  await expect(reserve).toContainText('Amber Glow Faceted')
  await reserve.getByRole('button', { name: 'Confirm' }).click()
  await expect(reserve).toContainText(/Reserved GB-\d{4}/)
  const sku = (await reserve.getByText(/Reserved GB-\d{4}/).textContent())!.match(/GB-\d{4}/)![0]

  // 5. Model + drawing.
  // The chat offers the next step once the SKU is reserved.
  await page.getByRole('button', { name: `Generate the design files for ${sku}` }).click()
  const generate = page.getByRole('article', { name: 'Generate design files' })
  await expect(generate).toContainText(sku)
  await generate.getByRole('button', { name: 'Confirm' }).click()
  await expect(generate).toContainText(`Files written for ${sku} rev A`, { timeout: 60_000 })
  await expect(generate).toContainText(`${sku}_A_drawing.pdf`)
  await expect(page.locator(`iframe[title="Technical drawing ${sku} rev A"]`)).toBeVisible()
  await snap(page, '3-drawing')
  const pdf = await page.request.get(`/api/designs/${sku}/A/files/drawing`)
  expect(pdf.ok()).toBe(true)
  expect(pdf.headers()['content-type']).toBe('application/pdf')

  // 6. Render: queued by the click, followed live until done.
  await page.getByRole('button', { name: `Render ${sku} rev A for the catalog` }).click()
  const render = page.getByRole('article', { name: 'Queue catalog render' })
  await render.getByRole('button', { name: 'Confirm' }).click()
  await expect(render).toContainText(/Render job #\d+: (queued|rendering|done)/)
  await expect(page.getByRole('tab', { name: 'Renders' })).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByRole('img', { name: new RegExp(`Render of ${sku}`) })).toBeVisible()
  await snap(page, '4-render')

  // The catalog shows the new SKU with its drawing.
  await page.getByRole('button', { name: 'Catalog' }).click()
  const row = page.getByRole('row', { name: new RegExp(sku) })
  await expect(row).toContainText('Amber Glow Faceted')
  await expect(row.getByRole('link', { name: 'Rev A' })).toBeVisible()
  await snap(page, '5-catalog')
})

/** The same flow without the assistant: the panel's buttons open the cards. */
test('a designer reserves, generates and renders from the panel alone', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('combobox', { name: 'Family' }).click()
  await page.getByRole('option', { name: /Round/ }).click()
  await expect(page.getByText(/Meets the Product Design Manual/)).toBeVisible()
  await expect(page.getByRole('button', { name: 'Render…' })).toBeDisabled()

  // Reserve: a name that breaks GEN-03 cannot be sent; the live check says why.
  await page.getByRole('button', { name: 'Reserve SKU…' }).click()
  const reserveForm = page.getByRole('form', { name: 'Reserve SKU…' })
  await reserveForm.getByLabel('Product name').fill('blue bead')
  await expect(reserveForm).toContainText('GEN-03')
  await expect(reserveForm.getByRole('button', { name: 'Review & confirm' })).toBeDisabled()
  await reserveForm.getByLabel('Product name').fill('Harbor Light Round')
  await reserveForm.getByLabel('Collection').selectOption('Coastal Garden')
  await expect(reserveForm).toContainText('Free in the catalog and follows GEN-03.')
  await reserveForm.getByRole('button', { name: 'Review & confirm' }).click()
  const reserve = page.getByRole('article', { name: 'Reserve SKU in SAP' })
  await reserve.getByRole('button', { name: 'Confirm' }).click()
  await expect(reserve).toContainText(/Reserved GB-\d{4}/)
  const sku = (await reserve.getByText(/Reserved GB-\d{4}/).textContent())!.match(/GB-\d{4}/)![0]

  // Generate: the SKU comes from the reservation.
  await page.getByRole('button', { name: 'Generate files…' }).click()
  const generateForm = page.getByRole('form', { name: 'Generate files…' })
  await expect(generateForm.getByLabel('SKU')).toHaveValue(sku)
  await generateForm.getByRole('button', { name: 'Review & confirm' }).click()
  const generate = page.getByRole('article', { name: 'Generate design files' })
  await generate.getByRole('button', { name: 'Confirm' }).click()
  await expect(generate).toContainText(`Files written for ${sku} rev A`, { timeout: 60_000 })
  await expect(page.locator(`iframe[title="Technical drawing ${sku} rev A"]`)).toBeVisible()

  // Render in the color chosen in the viewer.
  await page.getByRole('radio', { name: 'Sea Green' }).click()
  await page.getByRole('button', { name: 'Render…' }).click()
  const renderForm = page.getByRole('form', { name: 'Render…' })
  await expect(renderForm).toContainText('Sea Green')
  await renderForm.getByRole('button', { name: 'Review & confirm' }).click()
  const render = page.getByRole('article', { name: 'Queue catalog render' })
  await expect(render).toContainText('sea_green')
  await render.getByRole('button', { name: 'Confirm' }).click()
  await expect(page.getByRole('img', { name: new RegExp(`Render of ${sku}`) })).toBeVisible()
})

/**
 * Demo mode (decision 0022): no script, so the real DemoClient answers from the Q&A bank,
 * through the real tools, and never opens a card.
 */
test('demo mode answers a design chip, a manual question and an off-topic message', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('Demo mode · scripted answers')).toBeVisible()

  // The first example chip: the panel shows the proposal, highlighted, checked by the code.
  await page.getByRole('button', { name: 'A 10 mm faceted amber bead for the Amber Hollow collection' }).click()
  await page.getByRole('button', { name: 'Send' }).click()
  const answers = page.locator('[data-role="assistant"]')
  await expect(answers.last()).toContainText('I put a Faceted in the panel: Diameter 10.0 mm')
  await expect(answers.last()).toContainText('amber')
  await expect(page.getByLabel('Diameter', { exact: false }).first()).toHaveValue('10')
  await expect(page.locator('[data-proposed]').first()).toBeVisible()
  await expect(page.getByText(/Meets the Product Design Manual/)).toBeVisible()

  // A question about the manual: the rule id, and no card.
  await page.getByLabel('Describe the bead or charm…').fill("What's the smallest hole?")
  await page.getByRole('button', { name: 'Send' }).click()
  await expect(answers.last()).toContainText('GB-01')
  await expect(page.getByRole('article')).toHaveCount(0)

  // In Spanish, an off-topic message gets the Spanish redirect.
  await page.getByRole('button', { name: 'Español' }).click()
  await page.getByLabel('Describe la cuenta o el dije…').fill('Cuéntame un chiste')
  await page.getByRole('button', { name: 'Enviar' }).click()
  await expect(answers.last()).toContainText('solo ayudo a diseñar cuentas de vidrio y dijes')
  await expect(page.getByRole('article')).toHaveCount(0)
})
