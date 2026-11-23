import { describe, expect, it } from 'vitest'

import { parseSse } from '@/api/client'
import type { PendingAction, Validation } from '@/api/types'

import {
  currentStep,
  focusTarget,
  initialState,
  paramsDiff,
  paramsKey,
  studioReducer,
  type StudioState,
  type WorkflowInput,
  workflowSteps,
} from './state'

const validation = (params: Validation['params']): Validation => ({
  valid: true,
  family: 'FAC',
  params,
  violations: [],
  notes: [],
  rule_edition: '2026.1',
})

const action = (kind: PendingAction['kind'], extra: Partial<PendingAction> = {}): PendingAction => ({
  id: `a-${kind}`,
  conversation_id: 'c1',
  kind,
  status: 'pending',
  payload: {},
  result: null,
  created_at: '2026-11-18T10:00:00Z',
  expires_at: '2999-01-01T00:00:00Z',
  decided_at: null,
  ...extra,
})

function run(...actions: Parameters<typeof studioReducer>[1][]): StudioState {
  return actions.reduce(studioReducer, initialState)
}

describe('focusTarget', () => {
  const open = (a: PendingAction) => ({ type: 'event', event: { type: 'pending_action', data: { action: a } } }) as const

  it('is nothing without a pending card', () => {
    expect(focusTarget(initialState)).toBeNull()
    expect(focusTarget(run(open(action('reserve_sku', { status: 'confirmed' }))))).toBeNull()
  })

  it('is the newest pending card; the older one once the newest is set aside', () => {
    const state = run(open(action('reserve_sku')), open(action('generate_design')))
    expect(focusTarget(state)).toEqual({ kind: 'card', actionId: 'a-generate_design' })
    const aside = studioReducer(state, { type: 'dismiss', actionId: 'a-generate_design' })
    expect(focusTarget(aside)).toEqual({ kind: 'card', actionId: 'a-reserve_sku' })
    const back = studioReducer(aside, { type: 'refocus', actionId: 'a-generate_design' })
    expect(focusTarget(back)).toEqual({ kind: 'card', actionId: 'a-generate_design' })
  })

  it('waits while the assistant answers, and lets go of an expired card', () => {
    expect(focusTarget(run({ type: 'send', text: 'hi' }, open(action('reserve_sku'))))).toBeNull()
    const card = action('reserve_sku', { expires_at: '2026-11-18T10:15:00Z' })
    const state = run(open(card))
    expect(focusTarget(state, Date.parse('2026-11-18T10:10:00Z'))).not.toBeNull()
    expect(focusTarget(state, Date.parse('2026-11-18T10:16:00Z'))).toBeNull()
  })

  it('the Start-over question comes before any card', () => {
    const state = run(open(action('reserve_sku')), { type: 'ask', question: 'reset' })
    expect(focusTarget(state)).toEqual({ kind: 'reset' })
    expect(focusTarget(studioReducer(state, { type: 'ask', question: null }))).toEqual({ kind: 'card', actionId: 'a-reserve_sku' })
  })
})

describe('studioReducer', () => {
  it('fills the panel from a proposal and highlights the proposed values', () => {
    const state = run({
      type: 'event',
      event: {
        type: 'parameter_proposal',
        data: { family: 'FAC', validation: validation({ diameter_mm: 10, color: 'amber' }) },
      },
    })

    expect(state.family).toBe('FAC')
    expect(state.params).toEqual({ diameter_mm: 10, color: 'amber' })
    expect(state.proposed.sort()).toEqual(['color', 'diameter_mm'])
  })

  it('stops highlighting a value once the designer edits it', () => {
    const state = run(
      {
        type: 'event',
        event: {
          type: 'parameter_proposal',
          data: { family: 'FAC', validation: validation({ diameter_mm: 10, color: 'amber' }) },
        },
      },
      { type: 'edit', name: 'diameter_mm', value: 12 },
    )

    expect(state.params.diameter_mm).toBe(12)
    expect(state.proposed).toEqual(['color'])
  })

  it('a new family clears the panel; defaults fill it only while it is empty', () => {
    const state = run(
      { type: 'chooseFamily', family: 'RND' },
      { type: 'fillDefaults', family: 'RND', params: { diameter_mm: 8 } },
      { type: 'edit', name: 'diameter_mm', value: 9 },
      { type: 'fillDefaults', family: 'RND', params: { diameter_mm: 8 } },
    )

    expect(state.params).toEqual({ diameter_mm: 9 })
  })

  it('groups the tool calls of a turn and records their results', () => {
    const state = run(
      { type: 'send', text: 'hi' },
      { type: 'event', event: { type: 'tool_call', data: { id: 't1', name: 'list_families', arguments: {} } } },
      { type: 'event', event: { type: 'tool_call', data: { id: 't2', name: 'describe_family', arguments: {} } } },
      {
        type: 'event',
        event: { type: 'tool_result', data: { id: 't2', name: 'describe_family', ok: false, result: {} } },
      },
    )

    const steps = state.items.at(-1)
    expect(steps?.kind).toBe('steps')
    if (steps?.kind !== 'steps') return
    expect(steps.steps.map((s) => s.name)).toEqual(['list_families', 'describe_family'])
    expect(steps.steps[1].ok).toBe(false)
  })

  it('only a confirmed card changes what the studio has', () => {
    const pending = action('reserve_sku')
    const opened = run({ type: 'event', event: { type: 'pending_action', data: { action: pending } } })
    expect(opened.reserved).toBeNull()

    const cancelled = studioReducer(opened, {
      type: 'decided',
      action: { ...pending, status: 'cancelled' },
    })
    expect(cancelled.reserved).toBeNull()

    const confirmed = studioReducer(opened, {
      type: 'decided',
      action: { ...pending, status: 'confirmed', result: { ok: true, sku: 'GB-1034', sap_material: '50000134' } },
    })
    expect(confirmed.reserved).toEqual({ sku: 'GB-1034', name: undefined, sapMaterial: '50000134' })
  })

  it('a card the server returns again is updated, not drawn twice', () => {
    const pending = action('reserve_sku')
    const state = run(
      { type: 'event', event: { type: 'pending_action', data: { action: pending } } },
      { type: 'event', event: { type: 'pending_action', data: { action: { ...pending, payload: { name: 'Sol' } } } } },
    )

    expect(state.items.filter((item) => item.kind === 'action')).toHaveLength(1)
    expect(state.actions[pending.id].payload).toEqual({ name: 'Sol' })
  })

  it('reset starts a new design from scratch', () => {
    const state = run(
      { type: 'chooseFamily', family: 'FAC' },
      { type: 'send', text: 'hi' },
      { type: 'event', event: { type: 'conversation', data: { id: 'c1' } } },
      { type: 'reset' },
    )

    expect(state).toEqual(initialState)
  })

  it('a generated design opens the drawing tab; a queued render the renders tab', () => {
    const generated = run({
      type: 'decided',
      action: action('generate_design', { status: 'confirmed', result: { ok: true, sku: 'GB-1034', rev: 'A' } }),
    })
    expect(generated.design).toEqual({ sku: 'GB-1034', rev: 'A' })
    expect(generated.tab).toBe('drawing')

    const rendered = studioReducer(generated, {
      type: 'decided',
      action: action('render', { status: 'confirmed', result: { ok: true, job_id: 7 } }),
    })
    expect(rendered.renderJobs).toEqual([7])
    expect(rendered.tab).toBe('renders')
  })

  it('a failed confirmation changes nothing but the card', () => {
    const state = run({
      type: 'decided',
      action: action('generate_design', { status: 'failed', result: { ok: false, message: 'GB-03' } }),
    })
    expect(state.design).toBeNull()
    expect(state.actions['a-generate_design'].status).toBe('failed')
  })
})

describe('currentStep', () => {
  it('follows the design flow', () => {
    expect(currentStep(initialState)).toBe(0)
    expect(currentStep({ ...initialState, family: 'FAC' })).toBe(1)
    expect(currentStep({ ...initialState, family: 'FAC', actions: { a: action('reserve_sku') } })).toBe(2)
    expect(currentStep({ ...initialState, reserved: { sku: 'GB-1034' } })).toBe(3)
    expect(currentStep({ ...initialState, design: { sku: 'GB-1034', rev: 'A' } })).toBe(4)
  })
})

describe('parseSse', () => {
  it('parses complete events and keeps the incomplete tail', () => {
    const text =
      'event: conversation\ndata: {"id":"c1"}\n\nevent: message\r\ndata: {"role":"assistant","content":"Hola"}\r\n\r\nevent: done\ndata: {"sta'

    const { events, rest } = parseSse(text)

    expect(events).toEqual([
      { type: 'conversation', data: { id: 'c1' } },
      { type: 'message', data: { role: 'assistant', content: 'Hola' } },
    ])
    expect(rest).toBe('event: done\ndata: {"sta')
  })

  it('skips malformed events and comments', () => {
    const { events } = parseSse(': keep-alive\n\nevent: message\ndata: {nope\n\n')
    expect(events).toEqual([])
  })
})

describe('paramsKey', () => {
  it('does not depend on key order', () => {
    expect(paramsKey({ a: 1, b: 'x' })).toBe(paramsKey({ b: 'x', a: 1 }))
  })
})

describe('paramsDiff', () => {
  const parameters = {
    diameter_mm: { type: 'number' as const, label: 'Diameter', unit: 'mm', rules: [] },
    has_star: { type: 'boolean' as const, label: 'Star', rules: [] },
    color: { type: 'string' as const, label: 'Color', rules: [] },
  }

  it('lists the changed fields with labels, units and old → new values, in key order', () => {
    const diff = paramsDiff(
      { diameter_mm: 20, has_star: true, color: 'amber' },
      { color: 'cobalt', diameter_mm: 12, has_star: true },
      parameters,
    )
    expect(diff).toEqual([
      { key: 'color', label: 'Color', unit: undefined, old: 'amber', new: 'cobalt' },
      { key: 'diameter_mm', label: 'Diameter', unit: 'mm', old: 20, new: 12 },
    ])
  })

  it('ignores float noise and key order, and parameters the panel does not hold', () => {
    expect(paramsDiff({ diameter_mm: 10.0004, color: 'amber', hole_mm: 1.5 }, { color: 'amber', diameter_mm: 10 }, parameters)).toEqual([])
  })

  it('falls back to the key when the family has no label for it', () => {
    expect(paramsDiff({ x: 1 }, { x: 2 }, {})[0].label).toBe('x')
  })
})

describe('workflowSteps', () => {
  const base: WorkflowInput = { reserved: null, design: null, renderJob: null, paramsValid: true, stale: false }
  const statuses = (input: Partial<WorkflowInput>) => workflowSteps({ ...base, ...input }).map((s) => s.status)

  it('a fresh session: reserve is current, generate and render are blocked with reasons', () => {
    const steps = workflowSteps(base)
    expect(steps.map((s) => s.status)).toEqual(['current', 'blocked', 'blocked'])
    expect(steps[1].reason).toBe('needSku')
    expect(steps[2].reason).toBe('needDesign')
  })

  it('moves on as cards are confirmed', () => {
    const reserved = { sku: 'GB-1034', name: 'Amber Glow Faceted' }
    const design = { sku: 'GB-1034', rev: 'A' }
    expect(statuses({ reserved })).toEqual(['done', 'current', 'blocked'])
    expect(statuses({ reserved, design })).toEqual(['done', 'done', 'current'])
    expect(statuses({ reserved, design, renderJob: { id: 4, status: 'done', rev: 'A' } })).toEqual(['done', 'done', 'done'])
  })

  it('a queued or running render is in progress, a failed one is an error; only done is done', () => {
    const at = (status: 'queued' | 'running' | 'done' | 'failed') =>
      workflowSteps({ ...base, reserved: { sku: 'GB-1034' }, design: { sku: 'GB-1034', rev: 'A' }, renderJob: { id: 4, status, rev: 'A' } })[2].status
    expect(at('queued')).toBe('running')
    expect(at('running')).toBe('running')
    expect(at('done')).toBe('done')
    expect(at('failed')).toBe('failed')
  })

  it('a render of an older revision does not count for the newest one', () => {
    const steps = workflowSteps({
      ...base,
      reserved: { sku: 'GB-1034' },
      design: { sku: 'GB-1034', rev: 'B' },
      renderJob: { id: 5, status: 'done', rev: 'A' },
    })
    expect(steps[2]).toMatchObject({ status: 'current', olderRender: true })
    expect(workflowSteps({ ...base, design: { sku: 'GB-1034', rev: 'B' }, renderJob: { id: 6, status: 'done', rev: 'B' } })[2]).toMatchObject({
      status: 'done',
      olderRender: false,
    })
  })

  it('an existing SKU counts as step 1 done once its files are generated', () => {
    expect(statuses({ design: { sku: 'GB-1005', rev: 'C' } })).toEqual(['done', 'done', 'current'])
  })

  it('invalid parameters block generation', () => {
    const steps = workflowSteps({ ...base, reserved: { sku: 'GB-1034' }, paramsValid: false })
    expect(steps[1]).toMatchObject({ status: 'blocked', reason: 'needValid' })
  })

  it('stale files warn on generate and render but block neither', () => {
    const steps = workflowSteps({ ...base, reserved: { sku: 'GB-1034' }, design: { sku: 'GB-1034', rev: 'A' }, stale: true })
    expect(steps[1]).toMatchObject({ status: 'done', warning: 'stale' })
    expect(steps[2]).toMatchObject({ status: 'current', warning: 'rendersSaved' })
  })
})

describe('setParams', () => {
  it('replaces the whole panel and clears the proposal highlight', () => {
    const state: StudioState = { ...initialState, family: 'FAC', params: { diameter_mm: 12 }, proposed: ['diameter_mm'] }
    const next = studioReducer(state, { type: 'setParams', params: { diameter_mm: 10, hole_mm: 1.5 } })
    expect(next.params).toEqual({ diameter_mm: 10, hole_mm: 1.5 })
    expect(next.proposed).toEqual([])
  })
})

