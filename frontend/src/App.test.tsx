import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { FamilyInfo, PendingAction, Validation } from '@/api/types'
import i18n from '@/i18n'

import App from './App'

// jsdom has no WebGL: the three.js canvas is replaced by a stub in unit tests.
vi.mock('@/viewer/BeadPreview', () => ({
  BeadPreview: ({ label, url }: { label: string; url: string }) => (
    <div role="img" aria-label={label} data-url={url} />
  ),
}))

const FAC: FamilyInfo = {
  code: 'FAC',
  kind: 'glass_bead',
  name: 'Faceted bead',
  name_suffix: 'Faceted',
  material: 'Borosilicate glass',
  density_g_cm3: 2.23,
  parameters: {
    diameter_mm: { type: 'number', label: 'Diameter', unit: 'mm', minimum: 4, maximum: 16, step: 0.1, rules: ['GB-01'] },
    hole_mm: { type: 'number', label: 'Hole', unit: 'mm', minimum: 0.8, maximum: 3, step: 0.1, rules: ['GB-02'] },
    color: { type: 'string', label: 'Color', rules: ['GB-07'], enum: ['amber', 'cobalt'] },
  },
  defaults: { diameter_mm: 10, hole_mm: 1.5, color: 'amber' },
  option_parameter: 'color',
  collections: ['Permanente', 'Coastal Garden', 'Amber Hollow'],
  swatches: [
    { id: 'amber', name: 'Amber', hex: '#c9822b', transmission: 0.85, metallic: 0, roughness: 0.05 },
    { id: 'cobalt', name: 'Cobalt', hex: '#2f45b5', transmission: 0.8, metallic: 0, roughness: 0.05 },
  ],
}

const valid = (params: Validation['params']): Validation => ({
  valid: true,
  family: 'FAC',
  params,
  violations: [],
  notes: [],
  rule_edition: '2026.1',
})

const PROPOSED = { diameter_mm: 10, hole_mm: 1.5, color: 'amber' }

const reserveCard: PendingAction = {
  id: 'act1',
  conversation_id: 'conv1',
  kind: 'reserve_sku',
  status: 'pending',
  payload: { family: 'FAC', name: 'Amber Glow Faceted', collection: 'Amber Hollow', kind: 'glass_bead' },
  result: null,
  created_at: '2026-11-18T10:00:00Z',
  expires_at: '2999-01-01T00:00:00Z',
  decided_at: null,
}

function sse(events: [string, unknown][]): string {
  return events.map(([type, data]) => `event: ${type}\ndata: ${JSON.stringify(data)}\n\n`).join('')
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

/** A stand-in backend: routes by method and path. */
function backend(overrides: Record<string, (init?: RequestInit) => Response> = {}) {
  const calls: { method: string; url: string; body?: unknown }[] = []
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    const method = init?.method ?? 'GET'
    calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined })
    const path = url.split('?')[0]
    const key = `${method} ${path}`
    if (overrides[key]) return overrides[key](init)
    if (key === 'GET /api/health') return json({ status: 'ok', version: '0.1.0', llm_provider: 'fake' })
    if (key === 'GET /api/families')
      return json([
        { code: 'FAC', kind: 'glass_bead', name: 'Faceted bead', sku_prefix: 'GB' },
        { code: 'CRS', kind: 'charm', name: 'Crescent charm', sku_prefix: 'CH' },
      ])
    if (key === 'GET /api/families/FAC') return json(FAC)
    if (key === 'POST /api/preview') {
      const { params } = JSON.parse(String(init?.body)) as { params: Validation['params'] }
      if (Number(params.hole_mm) < 0.8) {
        return json({
          validation: {
            ...valid(params),
            valid: false,
            violations: [
              {
                rule: 'GB-02',
                parameters: ['hole_mm'],
                message: 'The hole must fit the 0.8 mm mandrel.',
                nearest_valid: [{ parameter: 'hole_mm', value: 0.8 }],
              },
            ],
          },
          preview: null,
        })
      }
      return json({
        validation: valid(params),
        preview: {
          preview_id: 'p2',
          url: '/api/previews/p2.glb',
          family: 'FAC',
          params,
          measurements: { volume_mm3: 420.5, mass_g: 0.938, material: 'borosilicate', density_g_cm3: 2.23, bbox_mm: [10, 10, 7] },
        },
      })
    }
    if (key === 'POST /api/chat')
      return new Response(
        sse([
          ['conversation', { id: 'conv1' }],
          ['tool_call', { id: 't1', name: 'propose_parameters', arguments: {} }],
          ['tool_result', { id: 't1', name: 'propose_parameters', ok: true, result: {} }],
          ['parameter_proposal', { family: 'FAC', validation: valid(PROPOSED) }],
          ['preview', {
            preview_id: 'p1',
            url: '/api/previews/p1.glb',
            family: 'FAC',
            params: PROPOSED,
            measurements: { volume_mm3: 400, mass_g: 0.892, material: 'borosilicate', density_g_cm3: 2.23, bbox_mm: [10, 10, 7] },
          }],
          ['tool_call', { id: 't2', name: 'request_reserve_sku', arguments: {} }],
          ['tool_result', { id: 't2', name: 'request_reserve_sku', ok: true, result: {} }],
          ['pending_action', { action: reserveCard }],
          ['message', { role: 'assistant', content: 'Here is a **10 mm** faceted bead. Confirm the card to reserve a SKU.' }],
          ['done', { conversation_id: 'conv1', run_id: 1, status: 'ok' }],
        ]),
        { headers: { 'Content-Type': 'text/event-stream' } },
      )
    if (key === 'POST /api/actions/act1/confirm')
      return json({
        ...reserveCard,
        status: 'confirmed',
        result: { ok: true, sku: 'GB-1034', sap_material: '50000134', name: 'Amber Glow Faceted', status: 'IN_DESIGN' },
      })
    if (key === 'GET /api/gallery') return json({ generated_at: null, renders: [] })
    if (key === 'POST /api/actions') {
      const body = JSON.parse(String(init?.body)) as { name?: string }
      if (body.name === 'amber bead')
        return json(
          {
            detail: 'The name breaks GEN-03.',
            result: { violations: [{ rule: 'GEN-03', message: "the last word must be 'Faceted'" }] },
          },
          422,
        )
      return json({ conversation_id: 'conv9', action: { ...reserveCard, conversation_id: 'conv9' } })
    }
    return json({ detail: `unexpected ${key}` }, 404)
  })
  vi.stubGlobal('fetch', fetchMock)
  return calls
}

function renderApp() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  )
}

describe('App', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('en')
    try {
      localStorage.clear()
    } catch {
      // no storage in this environment
    }
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows the title, the backend status and the demo guide', async () => {
    backend()

    renderApp()

    expect(screen.getByRole('heading', { name: 'Bead Studio' })).toBeInTheDocument()
    expect(await screen.findByText('ok (v0.1.0, LLM: fake)')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'How this demo works' })).toBeInTheDocument()
  })

  it('says when the backend is not reachable', async () => {
    backend({ 'GET /api/health': () => new Response('', { status: 502 }) })

    renderApp()

    expect(await screen.findByText('not reachable')).toBeInTheDocument()
  })

  it('switches the interface to Spanish', async () => {
    backend()

    renderApp()
    fireEvent.click(screen.getByRole('button', { name: 'Español' }))

    expect(await screen.findByText('Hilda & Luna Beadworks · Diseño de Producto')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Asistente de diseño' })).toBeInTheDocument()
  })

  it('description → proposed parameters → 3D preview → card → confirm reserves the SKU', async () => {
    const calls = backend()
    renderApp()

    fireEvent.change(screen.getByLabelText('Describe the bead or charm…'), {
      target: { value: 'A 10 mm faceted amber bead' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    // The answer, with bold text rendered as an element, never as HTML.
    expect(await screen.findByText('10 mm')).toContainHTML('10 mm')
    // The proposed values fill the panel and stay highlighted.
    const diameter = await screen.findByLabelText('Diameter')
    expect(diameter).toHaveValue(10)
    expect(diameter.closest('[data-proposed]')).not.toBeNull()
    // The preview the assistant built is shown without a rebuild.
    const model = await screen.findByRole('img', { name: '3D model of the Faceted bead' })
    expect(model).toHaveAttribute('data-url', '/api/previews/p1.glb')
    expect(screen.getByText('0.892 g')).toBeInTheDocument()

    // The chat sent the panel as data with the message.
    const chat = calls.find((c) => c.url === '/api/chat')
    expect(chat?.body).toMatchObject({ message: 'A 10 mm faceted amber bead', language: 'en' })

    // Nothing is reserved until the click.
    const card = await screen.findByRole('article', { name: 'Reserve SKU in SAP' })
    expect(calls.some((c) => c.url.includes('/confirm'))).toBe(false)
    fireEvent.click(within(card).getByRole('button', { name: 'Confirm' }))

    expect(await within(card).findByText('Reserved GB-1034')).toBeInTheDocument()
    expect(calls.filter((c) => c.url === '/api/actions/act1/confirm')).toHaveLength(1)

    // The next step is offered as a message to the assistant, not as an action.
    const next = await screen.findByRole('button', { name: 'Generate the design files for GB-1034' })
    expect(calls.some((c) => c.url.includes('/designs/'))).toBe(false)
    fireEvent.click(next)
    await waitFor(() =>
      expect(calls.filter((c) => c.url === '/api/chat').at(-1)?.body).toMatchObject({
        message: 'Generate the design files for GB-1034',
        conversation_id: 'conv1',
      }),
    )
  })

  it('a refused chat turn shows the reason the backend gives', async () => {
    const reason = "The assistant's daily budget for this demo is used up; it resets at 00:00 UTC."
    backend({ 'POST /api/chat': () => json({ detail: reason }, 429) })
    renderApp()

    fireEvent.change(screen.getByLabelText('Describe the bead or charm…'), {
      target: { value: 'A 10 mm faceted amber bead' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    expect(await screen.findByText(reason, { exact: false })).toBeInTheDocument()
  })

  it('an edit clears the highlight, revalidates, and shows the rule id with the nearest value', async () => {
    backend()
    renderApp()
    fireEvent.change(screen.getByLabelText('Describe the bead or charm…'), {
      target: { value: 'A faceted bead' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))
    const hole = await screen.findByLabelText('Hole')

    fireEvent.change(hole, { target: { value: '0.5' } })

    expect(hole.closest('[data-proposed]')).toBeNull()
    const alert = await screen.findByRole('alert', { name: 'Rule violations' })
    expect(within(alert).getByText('GB-02')).toBeInTheDocument()
    fireEvent.click(within(alert).getByRole('button', { name: 'hole_mm = 0.8' }))
    await waitFor(() => expect(screen.getByLabelText('Hole')).toHaveValue(0.8))
  })

  it('the panel opens a reserve card without the assistant; only Confirm reserves', async () => {
    const calls = backend()
    renderApp()

    fireEvent.click(await screen.findByRole('combobox', { name: 'Family' }))
    fireEvent.click(await screen.findByRole('option', { name: /Faceted bead/ }))
    expect(await screen.findByText(/Meets the Product Design Manual/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Reserve SKU…' }))
    const form = screen.getByRole('form', { name: 'Reserve SKU…' })
    fireEvent.change(within(form).getByLabelText('Product name'), { target: { value: 'amber bead' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Open card' }))
    expect(await within(form).findByRole('alert')).toHaveTextContent('GEN-03')

    fireEvent.change(within(form).getByLabelText('Product name'), { target: { value: 'Amber Glow Faceted' } })
    fireEvent.change(within(form).getByLabelText('Collection'), { target: { value: 'Amber Hollow' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Open card' }))

    const card = await screen.findByRole('article', { name: 'Reserve SKU in SAP' })
    expect(calls.filter((c) => c.url === '/api/actions').at(-1)?.body).toMatchObject({
      kind: 'reserve_sku',
      family: 'FAC',
      name: 'Amber Glow Faceted',
      collection: 'Amber Hollow',
      conversation_id: null,
    })
    expect(calls.some((c) => c.url.includes('/confirm'))).toBe(false)
    // Generate and render stay closed until there is something to generate or render.
    const render = screen.getByRole('button', { name: 'Render…' })
    expect(render).toBeDisabled()
    // The reason sits next to the action, and the button points to it.
    expect(render).toHaveAccessibleDescription('Generate the files first.')
    fireEvent.click(within(card).getByRole('button', { name: 'Confirm' }))
    expect(await within(card).findByText('Reserved GB-1034')).toBeInTheDocument()
  })
})
