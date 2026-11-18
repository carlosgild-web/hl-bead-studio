import { describe, expect, it } from 'vitest'

import { parseSse } from '@/api/client'
import type { PendingAction, Validation } from '@/api/types'

import { currentStep, initialState, paramsKey, studioReducer, type StudioState } from './state'

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
