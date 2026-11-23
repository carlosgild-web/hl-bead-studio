import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { FamilyInfo, PendingAction, Validation } from '@/api/types'
import i18n from '@/i18n'
import { resetRenderJobs } from '@/studio/context'

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

/** jsdom has no EventSource: a stand-in the tests can push render status events through. */
class FakeEventSource {
  static all: FakeEventSource[] = []
  onerror: (() => void) | null = null
  private listeners: Record<string, ((event: { data: string }) => void)[]> = {}
  readonly url: string
  constructor(url: string) {
    this.url = url
    FakeEventSource.all.push(this)
  }
  addEventListener(type: string, fn: (event: { data: string }) => void) {
    ;(this.listeners[type] ??= []).push(fn)
  }
  close() {}
  emit(type: string, data: unknown) {
    this.listeners[type]?.forEach((fn) => fn({ data: JSON.stringify(data) }))
  }
}

/** Send a status event for render job #4 to every open stream of it. */
function renderEvent(status: string, rev = 'A') {
  act(() => {
    FakeEventSource.all
      .filter((source) => source.url.includes('/renders/4/'))
      .forEach((source) => source.emit('status', { id: 4, status, sku: 'GB-1034', rev, finish: 'amber' }))
  })
}

function card(id: string, kind: PendingAction['kind'], payload: Record<string, unknown>): PendingAction {
  return { ...reserveCard, id, kind, payload, conversation_id: 'conv1' }
}

/** A stand-in backend: routes by method and path. Generated revisions are remembered. */
function backend(overrides: Record<string, (init?: RequestInit) => Response> = {}) {
  const calls: { method: string; url: string; body?: unknown }[] = []
  const opened: Record<string, PendingAction> = {}
  const designs: Record<string, Validation['params']> = {}
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
                message_es: 'El agujero debe ajustarse al mandril de 0,8 mm.',
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
    if (key === 'POST /api/names/check') {
      const { name } = JSON.parse(String(init?.body)) as { name: string }
      const fine = /^([A-Z][a-z]+ )+Faceted$/.test(name)
      return json({
        name,
        follows: fine,
        violations: fine
          ? []
          : [
              {
                rule: 'GEN-03',
                parameters: ['name'],
                message: `'${name}' does not follow the naming pattern.`,
                message_es: `'${name}' no sigue el patrón de nombres.`,
              },
            ],
        suggestion: fine ? null : 'Amber Glow Faceted',
        similar: [{ sku: 'GB-1006', name: 'Amber Drop Faceted', status: 'ACTIVE' }],
        sap_available: true,
      })
    }
    const confirm = /^POST \/api\/actions\/(gen-\w+|ren-\d+)\/confirm$/.exec(key)
    if (confirm) {
      const action = opened[confirm[1]]
      const p = action.payload as { sku: string; rev: string; params?: Validation['params'] }
      if (action.kind === 'generate_design') designs[p.rev] = p.params ?? {}
      const result =
        action.kind === 'generate_design' ? { ok: true, sku: p.sku, rev: p.rev } : { ok: true, job_id: 4, sku: p.sku, rev: p.rev }
      return json({ ...action, status: 'confirmed', result })
    }
    const design = /^GET \/api\/designs\/GB-1034\/(\w+)$/.exec(key)
    if (design && designs[design[1]]) {
      const revs = Object.keys(designs).sort()
      return json({
        sku: 'GB-1034',
        rev: design[1],
        family: 'FAC',
        name: 'Amber Glow Faceted',
        sap_material: '50000134',
        params: designs[design[1]],
        measurements: { volume_mm3: 400, mass_g: 0.892, material: 'borosilicate', density_g_cm3: 2.23, bbox_mm: [10, 10, 7] },
        drawing_scale: '5:1',
        generated_on: '2026-11-19',
        urls: { step: '/s', stl: '/t', glb: '/g', drawing: '/d' },
        next_rev: String.fromCharCode(revs.at(-1)!.charCodeAt(0) + 1),
      })
    }
    if (key === 'GET /api/renders/4')
      return json({ id: 4, status: 'queued', sku: 'GB-1034', rev: 'A', finish: 'amber', samples: 64, resolution: 1024 })
    if (key === 'POST /api/actions') {
      const body = JSON.parse(String(init?.body)) as { name?: string; kind: string; sku?: string; rev?: string; params?: Validation['params']; finish?: string }
      if (body.kind === 'generate_design') {
        const action = card(`gen-${body.rev}`, 'generate_design', { sku: body.sku, rev: body.rev, family: 'FAC', params: body.params })
        opened[action.id] = action
        return json({ conversation_id: 'conv1', action })
      }
      if (body.kind === 'render') {
        const action = card('ren-1', 'render', { sku: body.sku, rev: body.rev, finish: body.finish })
        opened[action.id] = action
        return json({ conversation_id: 'conv1', action })
      }
      if (body.name === 'amber bead Faceted')
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

/** A workflow step of the panel, by id. */
function stepOf(id: 'reserve' | 'generate' | 'render'): HTMLElement {
  const step = document.querySelector<HTMLElement>(`[data-step="${id}"]`)
  if (!step) throw new Error(`no step ${id}`)
  return step
}

/** After a reservation: Next step → Generate card → Confirm → Next step → Render card → Confirm. */
async function nextStepThroughRender(calls: { url: string; body?: unknown }[]) {
  fireEvent.click(await screen.findByRole('button', { name: 'Generate the design files for GB-1034' }))
  const generate = await screen.findByRole('article', { name: 'Generate design files' })
  expect(calls.filter((c) => c.url === '/api/actions').at(-1)?.body).toMatchObject({
    kind: 'generate_design',
    sku: 'GB-1034',
    rev: 'A',
    family: 'FAC',
  })
  fireEvent.click(within(generate).getByRole('button', { name: 'Confirm' }))
  expect(await within(generate).findByText('Files written for GB-1034 rev A')).toBeInTheDocument()

  fireEvent.click(await screen.findByRole('button', { name: 'Render GB-1034 rev A for the catalog' }))
  const render = await screen.findByRole('article', { name: 'Queue catalog render' })
  expect(calls.filter((c) => c.url === '/api/actions').at(-1)?.body).toMatchObject({
    kind: 'render',
    sku: 'GB-1034',
    rev: 'A',
    finish: 'amber',
  })
  fireEvent.click(within(render).getByRole('button', { name: 'Confirm' }))
  expect(await within(render).findByText('Render job #4: queued')).toBeInTheDocument()
  return render
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
    FakeEventSource.all = []
    resetRenderJobs()
    vi.stubGlobal('EventSource', FakeEventSource)
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

  it('shows the demo-mode badge and the question chips only in demo mode', async () => {
    backend({
      'GET /api/health': () =>
        json({ status: 'ok', version: '0.1.0', llm_provider: 'fake', llm_note: 'auto found no model.' }),
    })

    renderApp()

    const badge = await screen.findByText('Demo mode · scripted answers')
    expect(badge.getAttribute('title')).toMatch(/curated list of questions.*auto found no model\./)
    expect(screen.getByRole('button', { name: 'Which fonts can I use for an initial charm?' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: "What's the smallest hole I can put in a glass bead?" }))
    expect(screen.getByRole('textbox')).toHaveValue("What's the smallest hole I can put in a glass bead?")
  })

  it('shows no demo badge or question chips with a model', async () => {
    backend({ 'GET /api/health': () => json({ status: 'ok', version: '0.1.0', llm_provider: 'groq' }) })

    renderApp()

    expect(await screen.findByText('ok (v0.1.0, LLM: groq)')).toBeInTheDocument()
    expect(screen.queryByText('Demo mode · scripted answers')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Which fonts can I use for an initial charm?' })).toBeNull()
    expect(screen.getByRole('button', { name: /A 10 mm faceted amber bead/ })).toBeInTheDocument()
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

    // "Next step" opens the next card itself, without the assistant (any provider).
    const renderCard = await nextStepThroughRender(calls)
    expect(calls.filter((c) => c.url === '/api/chat')).toHaveLength(1)
    expect(screen.queryByText(/I only have scripted answers/)).toBeNull()
    // The workflow follows the same state; the render is in progress until the job is done,
    // and the chat card follows the job live.
    expect(stepOf('reserve')).toHaveAttribute('data-status', 'done')
    expect(within(stepOf('reserve')).getByText(/GB-1034 · Amber Glow Faceted reserved/)).toBeInTheDocument()
    expect(within(stepOf('generate')).getByText(/Rev A files written/)).toBeInTheDocument()
    expect(stepOf('render')).toHaveAttribute('data-status', 'running')
    renderEvent('running')
    expect(within(renderCard).getByText('Render job #4: rendering')).toBeInTheDocument()
    expect(stepOf('render')).toHaveAttribute('data-status', 'running')
    renderEvent('done')
    expect(within(renderCard).getByText('Render job #4: done')).toBeInTheDocument()
    expect(stepOf('render')).toHaveAttribute('data-status', 'done')
  })

  it('after Rev B, a render of Rev A no longer counts and is labelled as older', async () => {
    const calls = backend()
    renderApp()
    fireEvent.change(screen.getByLabelText('Describe the bead or charm…'), { target: { value: 'A faceted bead' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))
    const reserve = await screen.findByRole('article', { name: 'Reserve SKU in SAP' })
    fireEvent.click(within(reserve).getByRole('button', { name: 'Confirm' }))
    await nextStepThroughRender(calls)
    renderEvent('done')

    fireEvent.change(screen.getByLabelText('Diameter'), { target: { value: '12' } })
    const [notice] = await screen.findAllByRole('status', { name: 'Parameters changed since Rev A' })
    fireEvent.click(within(notice).getByRole('button', { name: 'Generate Rev B' }))
    await waitFor(() => expect(screen.getAllByRole('article', { name: 'Generate design files' })).toHaveLength(2))
    const revB = screen.getAllByRole('article', { name: 'Generate design files' }).at(-1)!
    fireEvent.click(within(revB).getByRole('button', { name: 'Confirm' }))
    expect(await within(revB).findByText('Files written for GB-1034 rev B')).toBeInTheDocument()

    await waitFor(() => expect(stepOf('render')).toHaveAttribute('data-status', 'current'))
    expect(stepOf('render')).toHaveTextContent('Last render: Rev A (job #4). Render Rev B for the catalog.')
    fireEvent.mouseDown(screen.getByRole('tab', { name: /Renders/ }), { button: 0 })
    expect(await screen.findByText('Rev A, older revision')).toBeInTheDocument()
  })

  it('the chip and the stepper open the same card once; the second click goes to it', async () => {
    backend()
    renderApp()
    fireEvent.change(screen.getByLabelText('Describe the bead or charm…'), { target: { value: 'A faceted bead' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))
    const reserve = await screen.findByRole('article', { name: 'Reserve SKU in SAP' })
    fireEvent.click(within(reserve).getByRole('button', { name: 'Confirm' }))

    fireEvent.click(await screen.findByRole('button', { name: 'Generate the design files for GB-1034' }))
    const generate = await screen.findByRole('article', { name: 'Generate design files' })
    // The server returns the open card again; the chat shows it once.
    fireEvent.click(within(generate).getByRole('button', { name: 'Not now' }))
    fireEvent.click(within(stepOf('generate')).getByRole('button', { name: 'Generate files…' }))
    const form = screen.getByRole('form', { name: 'Generate files…' })
    fireEvent.click(within(form).getByRole('button', { name: 'Review & confirm' }))
    expect(await within(stepOf('generate')).findByRole('button', { name: /Go to the card/ })).toBeInTheDocument()
    expect(screen.getAllByRole('article', { name: 'Generate design files' })).toHaveLength(1)
  })

  it('after a finished render, "Start a new design" clears the chat and the panel', async () => {
    const calls = backend()
    renderApp()
    fireEvent.change(screen.getByLabelText('Describe the bead or charm…'), { target: { value: 'A faceted bead' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))
    const reserve = await screen.findByRole('article', { name: 'Reserve SKU in SAP' })
    fireEvent.click(within(reserve).getByRole('button', { name: 'Confirm' }))
    await nextStepThroughRender(calls)
    expect(screen.queryByRole('button', { name: /Start a new design/ })).toBeNull() // still rendering
    renderEvent('done')

    fireEvent.click(await screen.findByRole('button', { name: /Start a new design/ }))
    const ask = screen.getByRole('alertdialog', { name: 'New design' })
    fireEvent.click(within(ask).getByRole('button', { name: 'Keep working' }))
    expect(screen.getAllByRole('article')).not.toHaveLength(0)

    fireEvent.click(screen.getByRole('button', { name: 'New design' }))
    fireEvent.click(within(screen.getByRole('alertdialog', { name: 'New design' })).getByRole('button', { name: 'Start over' }))
    expect(await screen.findByText(/Describe a glass bead or a charm/)).toBeInTheDocument()
    expect(screen.queryAllByRole('article')).toHaveLength(0)
    expect(document.querySelector('[data-step]')).toBeNull()

    // The next message starts a new conversation.
    fireEvent.change(screen.getByLabelText('Describe the bead or charm…'), { target: { value: 'A round bead' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))
    await waitFor(() => expect(calls.filter((c) => c.url === '/api/chat')).toHaveLength(2))
    expect(calls.filter((c) => c.url === '/api/chat').at(-1)?.body).toMatchObject({ conversation_id: null })
  })

  it('focus mode dims the studio around a waiting card until it is decided or set aside', async () => {
    backend()
    renderApp()
    fireEvent.change(screen.getByLabelText('Describe the bead or charm…'), { target: { value: 'A faceted bead' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))
    const reserve = await screen.findByRole('article', { name: 'Reserve SKU in SAP' })

    const panel = (await waitFor(() => stepOf('reserve'))).closest('[data-dimmed]')
    const input = screen.getByLabelText('Describe the bead or charm…').closest('form')!
    const answer = screen.getByText('10 mm').closest('[data-dimmed]')
    for (const region of [panel, input, answer, screen.getByRole('heading', { name: 'Bead Studio', level: 1 }).closest('header')]) {
      expect(region).toHaveAttribute('data-dimmed')
      expect(region).toHaveAttribute('inert')
    }
    expect(reserve.closest('[data-dimmed]')).toBeNull()
    expect(reserve).toHaveAttribute('data-focused')
    await waitFor(() => expect(within(reserve).getByRole('button', { name: 'Confirm' })).toHaveFocus())

    // "Not now" sets it aside; the stepper's "Go to the card" brings it back.
    fireEvent.click(within(reserve).getByRole('button', { name: 'Not now' }))
    expect(document.querySelector('[data-dimmed]')).toBeNull()
    expect(within(reserve).getByRole('button', { name: 'Confirm' })).toBeInTheDocument()
    fireEvent.click(within(stepOf('reserve')).getByRole('button', { name: /Go to the card/ }))
    expect(input).toHaveAttribute('data-dimmed')
    fireEvent.keyDown(reserve, { key: 'Escape' })
    expect(input).not.toHaveAttribute('data-dimmed')

    fireEvent.click(within(stepOf('reserve')).getByRole('button', { name: /Go to the card/ }))
    fireEvent.click(within(reserve).getByRole('button', { name: 'Confirm' }))
    expect(await within(reserve).findByText('Reserved GB-1034')).toBeInTheDocument()
    expect(document.querySelector('[data-dimmed]')).toBeNull()

    // The Start-over question dims the rest as well.
    fireEvent.click(screen.getByRole('button', { name: 'New design' }))
    expect(screen.getByRole('alertdialog', { name: 'New design' }).closest('[data-dimmed]')).toBeNull()
    expect(input).toHaveAttribute('data-dimmed')
    expect(reserve.closest('[data-dimmed]')).not.toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Keep working' }))
    expect(document.querySelector('[data-dimmed]')).toBeNull()
  })

  it('a fresh workflow starts at step 1, with steps 2 and 3 blocked', async () => {
    backend()
    renderApp()
    fireEvent.click(await screen.findByRole('combobox', { name: 'Family' }))
    fireEvent.click(await screen.findByRole('option', { name: /Faceted bead/ }))

    await waitFor(() => expect(stepOf('reserve')).toHaveAttribute('data-status', 'current'))
    expect(stepOf('generate')).toHaveAttribute('data-status', 'blocked')
    expect(within(stepOf('generate')).getByText('Reserve a SKU first, or type an existing one.')).toBeInTheDocument()
    expect(within(stepOf('generate')).getByRole('button', { name: 'Use an existing SKU…' })).toBeInTheDocument()
    expect(stepOf('render')).toHaveAttribute('data-status', 'blocked')
  })

  it('warns when the panel no longer matches the generated revision; revert or generate Rev B', async () => {
    const calls = backend()
    renderApp()
    fireEvent.change(screen.getByLabelText('Describe the bead or charm…'), { target: { value: 'A faceted bead' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))
    const reserve = await screen.findByRole('article', { name: 'Reserve SKU in SAP' })
    fireEvent.click(within(reserve).getByRole('button', { name: 'Confirm' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Generate the design files for GB-1034' }))
    const generate = await screen.findByRole('article', { name: 'Generate design files' })
    fireEvent.click(within(generate).getByRole('button', { name: 'Confirm' }))
    expect(await within(generate).findByText('Files written for GB-1034 rev A')).toBeInTheDocument()
    expect(screen.queryByRole('status', { name: 'Parameters changed since Rev A' })).toBeNull()

    fireEvent.change(screen.getByLabelText('Diameter'), { target: { value: '12' } })

    const [notice] = await screen.findAllByRole('status', { name: 'Parameters changed since Rev A' })
    expect(notice).toHaveTextContent('Diameter 10 → 12 mm')
    expect(screen.getAllByText('out of date').length).toBeGreaterThan(0)
    expect(stepOf('render')).toHaveTextContent('Renders the saved Rev A, not your current edits.')

    fireEvent.click(within(notice).getByRole('button', { name: 'Revert to Rev A parameters' }))
    await waitFor(() => expect(screen.queryByRole('status', { name: 'Parameters changed since Rev A' })).toBeNull())
    expect(screen.getByLabelText('Diameter')).toHaveValue(10)

    fireEvent.change(screen.getByLabelText('Diameter'), { target: { value: '12' } })
    const [again] = await screen.findAllByRole('status', { name: 'Parameters changed since Rev A' })
    fireEvent.click(within(again).getByRole('button', { name: 'Generate Rev B' }))
    await waitFor(() => expect(screen.getAllByRole('article', { name: 'Generate design files' })).toHaveLength(2))
    const revB = screen.getAllByRole('article', { name: 'Generate design files' }).at(-1)!
    // The panel says where the card went; the link focuses its Confirm button.
    const [opened] = screen.getAllByText('Card opened in the chat. Confirm it there.')
    fireEvent.click(within(opened.closest('[role="status"]') as HTMLElement).getByRole('button', { name: 'Go to the card' }))
    expect(document.activeElement).toBe(within(revB).getByRole('button', { name: 'Confirm' }))
    expect(calls.filter((c) => c.url === '/api/actions').at(-1)?.body).toMatchObject({ kind: 'generate_design', rev: 'B' })
    fireEvent.click(within(revB).getByRole('button', { name: 'Confirm' }))
    expect(await within(revB).findByText('Files written for GB-1034 rev B')).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByRole('status', { name: /Parameters changed since/ })).toBeNull())
    expect(screen.queryByText('Card opened in the chat. Confirm it there.')).toBeNull()
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

  it('in Spanish the panel shows the rule message in Spanish', async () => {
    await i18n.changeLanguage('es')
    backend()
    renderApp()
    fireEvent.change(screen.getByLabelText('Describe la cuenta o el dije…'), {
      target: { value: 'Una cuenta facetada' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Enviar' }))
    const hole = await screen.findByLabelText('Hole')

    fireEvent.change(hole, { target: { value: '0.5' } })

    const alert = await screen.findByRole('alert', { name: 'Reglas incumplidas' })
    expect(within(alert).getByText(/El agujero debe ajustarse/)).toBeInTheDocument()
    expect(within(alert).queryByText(/The hole must fit/)).toBeNull()
  })

  it('the name field adds the family word and checks the name while typing', async () => {
    const calls = backend()
    renderApp()
    fireEvent.click(await screen.findByRole('combobox', { name: 'Family' }))
    fireEvent.click(await screen.findByRole('option', { name: /Faceted bead/ }))
    fireEvent.click(await screen.findByRole('button', { name: 'Reserve SKU…' }))
    const form = screen.getByRole('form', { name: 'Reserve SKU…' })

    fireEvent.change(within(form).getByLabelText('Product name'), { target: { value: 'amber glow' } })

    expect(within(form).getByText('amber glow Faceted')).toBeInTheDocument()
    expect(await within(form).findByText(/does not follow the naming pattern/)).toBeInTheDocument()
    expect(within(form).getByText(/Amber Drop Faceted/)).toBeInTheDocument()
    fireEvent.click(within(form).getByRole('button', { name: 'Amber Glow Faceted' }))
    expect(within(form).getByLabelText('Product name')).toHaveValue('Amber Glow')
    expect(await within(form).findByText('Free in the catalog and follows GEN-03.')).toBeInTheDocument()
    expect(calls.some((c) => c.url === '/api/actions')).toBe(false) // checking opens nothing
  })

  it('the panel opens a reserve card without the assistant; only Confirm reserves', async () => {
    const calls = backend()
    renderApp()

    fireEvent.click(await screen.findByRole('combobox', { name: 'Family' }))
    fireEvent.click(await screen.findByRole('option', { name: /Faceted bead/ }))
    expect(await screen.findByText(/Meets the Product Design Manual/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Reserve SKU…' }))
    const form = screen.getByRole('form', { name: 'Reserve SKU…' })
    // A name that breaks GEN-03 cannot be sent; the check says why while typing.
    fireEvent.change(within(form).getByLabelText('Product name'), { target: { value: 'amber bead' } })
    expect(await within(form).findByText(/does not follow the naming pattern/)).toBeInTheDocument()
    expect(within(form).getByRole('button', { name: 'Review & confirm' })).toBeDisabled()

    fireEvent.change(within(form).getByLabelText('Product name'), { target: { value: 'Amber Glow Faceted' } })
    fireEvent.change(within(form).getByLabelText('Collection'), { target: { value: 'Amber Hollow' } })
    const submit = within(form).getByRole('button', { name: 'Review & confirm' })
    await waitFor(() => expect(submit).toBeEnabled())
    fireEvent.click(submit)

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
