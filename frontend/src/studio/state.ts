import type { ChatEvent, Params, ParamValue, PendingAction } from '@/api/types'

/** One tool the assistant used in a turn, shown collapsed under its answer. */
export interface ToolStep {
  id: string
  name: string
  arguments: Record<string, unknown>
  ok?: boolean
  result?: Record<string, unknown>
}

export type ChatItem =
  | { kind: 'user'; text: string }
  | { kind: 'assistant'; text: string }
  | { kind: 'steps'; steps: ToolStep[] }
  | { kind: 'action'; actionId: string }
  | { kind: 'error'; text: string }

export interface StudioState {
  family: string | null
  params: Params
  /** Parameters the assistant filled in that the designer has not touched yet. */
  proposed: string[]
  conversationId: string | null
  items: ChatItem[]
  actions: Record<string, PendingAction>
  busy: boolean
  reserved: { sku: string; name?: string; sapMaterial?: string } | null
  design: { sku: string; rev: string } | null
  renderJobs: number[]
  tab: 'drawing' | 'renders'
}

export const initialState: StudioState = {
  family: null,
  params: {},
  proposed: [],
  conversationId: null,
  items: [],
  actions: {},
  busy: false,
  reserved: null,
  design: null,
  renderJobs: [],
  tab: 'drawing',
}

export type StudioAction =
  | { type: 'chooseFamily'; family: string }
  | { type: 'fillDefaults'; family: string; params: Params }
  | { type: 'edit'; name: string; value: ParamValue }
  | { type: 'send'; text: string }
  | { type: 'event'; event: ChatEvent }
  | { type: 'failed'; text: string }
  | { type: 'decided'; action: PendingAction }
  | { type: 'tab'; tab: StudioState['tab'] }
  | { type: 'reset' }

function withSteps(items: ChatItem[], update: (steps: ToolStep[]) => ToolStep[]): ChatItem[] {
  const last = items.at(-1)
  if (last?.kind === 'steps') return [...items.slice(0, -1), { kind: 'steps', steps: update(last.steps) }]
  return [...items, { kind: 'steps', steps: update([]) }]
}

function onEvent(state: StudioState, event: ChatEvent): StudioState {
  switch (event.type) {
    case 'conversation':
      return { ...state, conversationId: event.data.id }
    case 'tool_call':
      return {
        ...state,
        items: withSteps(state.items, (steps) => [
          ...steps,
          { id: event.data.id, name: event.data.name, arguments: event.data.arguments },
        ]),
      }
    case 'tool_result':
      return {
        ...state,
        items: withSteps(state.items, (steps) =>
          steps.map((s) =>
            s.id === event.data.id ? { ...s, ok: event.data.ok, result: event.data.result } : s,
          ),
        ),
      }
    case 'parameter_proposal': {
      const proposal = event.data.validation.params
      const sameFamily = state.family === event.data.family
      return {
        ...state,
        family: event.data.family,
        params: sameFamily ? { ...state.params, ...proposal } : { ...proposal },
        proposed: [
          ...new Set([...(sameFamily ? state.proposed : []), ...Object.keys(proposal)]),
        ],
      }
    }
    case 'pending_action': {
      const action = event.data.action
      return {
        ...state,
        actions: { ...state.actions, [action.id]: action },
        items: [...state.items, { kind: 'action', actionId: action.id }],
      }
    }
    case 'message':
      return { ...state, items: [...state.items, { kind: 'assistant', text: event.data.content }] }
    case 'error':
      return { ...state, items: [...state.items, { kind: 'error', text: event.data.message }] }
    case 'done':
      return {
        ...state,
        busy: false,
        conversationId: event.data.conversation_id ?? state.conversationId,
      }
    default:
      // `thinking` and `preview` need no state here (the preview seeds the query cache).
      return state
  }
}

function onDecided(state: StudioState, action: PendingAction): StudioState {
  const next = { ...state, actions: { ...state.actions, [action.id]: action } }
  const result = action.result
  if (action.status !== 'confirmed' || !result?.ok) return next
  if (action.kind === 'reserve_sku' && result.sku) {
    next.reserved = { sku: result.sku, name: result.name, sapMaterial: result.sap_material }
  } else if (action.kind === 'generate_design' && result.sku && result.rev) {
    next.design = { sku: result.sku, rev: result.rev }
    next.tab = 'drawing'
  } else if (action.kind === 'render' && result.job_id !== undefined) {
    next.renderJobs = [result.job_id, ...state.renderJobs]
    next.tab = 'renders'
  }
  return next
}

export function studioReducer(state: StudioState, action: StudioAction): StudioState {
  switch (action.type) {
    case 'chooseFamily':
      if (action.family === state.family) return state
      return { ...state, family: action.family, params: {}, proposed: [] }
    case 'fillDefaults':
      if (action.family !== state.family || Object.keys(state.params).length > 0) return state
      return { ...state, params: { ...action.params } }
    case 'edit':
      return {
        ...state,
        params: { ...state.params, [action.name]: action.value },
        proposed: state.proposed.filter((name) => name !== action.name),
      }
    case 'send':
      return { ...state, busy: true, items: [...state.items, { kind: 'user', text: action.text }] }
    case 'event':
      return onEvent(state, action.event)
    case 'failed':
      return { ...state, busy: false, items: [...state.items, { kind: 'error', text: action.text }] }
    case 'decided':
      return onDecided(state, action.action)
    case 'tab':
      return { ...state, tab: action.tab }
    case 'reset':
      return initialState
  }
}

/** A stable text key for a parameter set (query keys must not depend on key order). */
export function paramsKey(params: Params): string {
  return JSON.stringify(Object.keys(params).sort().map((k) => [k, params[k]]))
}

/** The demo guide's "You are here": the next step of the design flow. */
export function currentStep(state: StudioState): number {
  if (state.design) return 4
  if (state.reserved) return 3
  if (Object.values(state.actions).some((a) => a.kind === 'reserve_sku')) return 2
  if (state.family) return 1
  return 0
}
