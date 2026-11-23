import type { ChatEvent, ParameterInfo, Params, ParamValue, PendingAction, RenderJob } from '@/api/types'

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
  /** A question to the designer outside the cards ("Start over?"). */
  asking: 'reset' | null
  /** Cards the designer set aside with "Use the chat": still pending, no longer in focus. */
  dismissed: string[]
  /** The workflow step whose form is open in the panel: the studio waits for it there. */
  openStep: StepId | null
  /** The step to open once the workflow can take it (after a SKU or files arrive). */
  wantStep: StepId | null
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
  asking: null,
  dismissed: [],
  openStep: null,
  wantStep: null,
}

export type StudioAction =
  | { type: 'chooseFamily'; family: string }
  | { type: 'fillDefaults'; family: string; params: Params }
  | { type: 'edit'; name: string; value: ParamValue }
  /** "Revert to Rev A parameters": the whole panel at once, from a saved revision. */
  | { type: 'setParams'; params: Params }
  | { type: 'send'; text: string }
  /** A restored card's status from the server; nothing else changes. */
  | { type: 'refreshAction'; action: PendingAction }
  | { type: 'event'; event: ChatEvent }
  | { type: 'failed'; text: string }
  | { type: 'decided'; action: PendingAction }
  | { type: 'tab'; tab: StudioState['tab'] }
  | { type: 'reset' }
  | { type: 'ask'; question: StudioState['asking'] }
  /** "Use the chat" on a card: it stays pending, the studio is no longer dimmed for it. */
  | { type: 'dismiss'; actionId: string }
  /** "Go to the card": the card is in focus again. */
  | { type: 'refocus'; actionId: string }
  /** Open a workflow step's form in the panel (or close it with null). */
  | { type: 'openStep'; step: StepId | null }
  | { type: 'wantStep'; step: StepId | null }

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
      // The server returns an open card again instead of a second one of its kind: the
      // card is updated, never drawn twice.
      const action = event.data.action
      const shown = state.items.some((item) => item.kind === 'action' && item.actionId === action.id)
      return {
        ...state,
        actions: { ...state.actions, [action.id]: action },
        items: shown ? state.items : [...state.items, { kind: 'action', actionId: action.id }],
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
    case 'setParams':
      return { ...state, params: { ...action.params }, proposed: [] }
    case 'send':
      return { ...state, busy: true, items: [...state.items, { kind: 'user', text: action.text }] }
    case 'event':
      return onEvent(state, action.event)
    case 'failed':
      return { ...state, busy: false, items: [...state.items, { kind: 'error', text: action.text }] }
    case 'decided':
      return onDecided(state, action.action)
    case 'refreshAction':
      return state.actions[action.action.id]
        ? { ...state, actions: { ...state.actions, [action.action.id]: action.action } }
        : state
    case 'tab':
      return { ...state, tab: action.tab }
    case 'reset':
      return initialState
    case 'ask':
      return { ...state, asking: action.question }
    case 'dismiss':
      return state.dismissed.includes(action.actionId)
        ? state
        : { ...state, dismissed: [...state.dismissed, action.actionId] }
    case 'refocus':
      return { ...state, dismissed: state.dismissed.filter((id) => id !== action.actionId) }
    case 'openStep':
      return { ...state, openStep: action.step }
    case 'wantStep':
      return { ...state, wantStep: action.step }
  }
}

// --- focus mode ---------------------------------------------------------------------------

/** What waits for the designer: the studio dims everything else around it. */
export type FocusTarget =
  | { kind: 'card'; actionId: string }
  | { kind: 'reset' }
  | { kind: 'step'; step: StepId }
  | null

export function isExpired(action: PendingAction, now = Date.now()): boolean {
  return action.status === 'pending' && new Date(action.expires_at).getTime() < now
}

/**
 * The decision the flow waits for: the Start-over question, else the newest pending card
 * in the chat that is not expired or set aside. None while the assistant is answering.
 */
export function focusTarget(state: StudioState, now = Date.now()): FocusTarget {
  if (state.busy) return null
  if (state.asking === 'reset') return { kind: 'reset' }
  for (let i = state.items.length - 1; i >= 0; i--) {
    const item = state.items[i]
    if (item.kind !== 'action') continue
    const action = state.actions[item.actionId]
    if (action?.status === 'pending' && !isExpired(action, now) && !state.dismissed.includes(action.id)) {
      return { kind: 'card', actionId: action.id }
    }
  }
  // An open step of the workflow waits for its form: the rest of the studio is dimmed.
  if (state.openStep) return { kind: 'step', step: state.openStep }
  return null
}

/** A stable text key for a parameter set (query keys must not depend on key order). */
/** The name SAP stores: what the designer typed, then the family word once (GEN-03). */
export function fullName(typed: string, suffix: string): string {
  const words = typed.split(/\s+/).filter(Boolean)
  if (words.at(-1)?.toLowerCase() === suffix.toLowerCase()) words.pop()
  return [...words, suffix].join(' ')
}

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

// --- the panel against the generated revision -----------------------------------------

export interface ParamChange {
  key: string
  label: string
  unit?: string
  old: ParamValue | undefined
  new: ParamValue
}

/** Numbers compared to 0.001 (the panel and params.json may differ in float noise). */
function normalized(value: ParamValue | undefined): ParamValue | undefined {
  return typeof value === 'number' ? Math.round(value * 1000) / 1000 : value
}

/**
 * What changed between a generated revision's parameters and the panel, in key order, with
 * the family's labels. A parameter the panel does not hold is not a change.
 */
export function paramsDiff(
  saved: Params,
  current: Params,
  parameters: Record<string, ParameterInfo>,
): ParamChange[] {
  return Object.keys({ ...saved, ...current })
    .sort()
    .filter((key) => current[key] !== undefined && normalized(saved[key]) !== normalized(current[key]))
    .map((key) => ({
      key,
      label: parameters[key]?.label ?? key,
      unit: parameters[key]?.unit,
      old: saved[key],
      new: current[key],
    }))
}

// --- the workflow stepper ---------------------------------------------------------------

export type StepId = 'reserve' | 'generate' | 'render'
export type StepStatus = 'current' | 'done' | 'blocked' | 'running' | 'failed'

export interface WorkflowStep {
  id: StepId
  status: StepStatus
  /** Why a blocked step is blocked (an i18n key under panel.actions). */
  reason: 'needSku' | 'needValid' | 'needDesign' | null
  /** A warning on a step that still works: the files are older than the panel. */
  warning: 'stale' | 'rendersSaved' | null
  /** Render only: the latest render is of an older revision than the generated one. */
  olderRender: boolean
}

export interface WorkflowInput {
  reserved: StudioState['reserved']
  design: StudioState['design']
  /** The newest render job of this session, if any: its revision and last known status. */
  renderJob: Pick<RenderJob, 'id' | 'status' | 'rev'> | null
  /** The panel's live check (undefined while there is none). */
  paramsValid: boolean | undefined
  /** The panel's parameters differ from the generated revision's. */
  stale: boolean
}

/**
 * The three steps of the design flow, derived from what the studio has (confirmed cards,
 * from the panel or from the assistant), never from which buttons were clicked.
 */
export function workflowSteps(input: WorkflowInput): WorkflowStep[] {
  const { reserved, design, renderJob, paramsValid, stale } = input
  const step = (
    id: StepId,
    status: StepStatus,
    reason: WorkflowStep['reason'] = null,
    warning: WorkflowStep['warning'] = null,
    olderRender = false,
  ) => ({ id, status, reason, warning, olderRender }) satisfies WorkflowStep

  const reserve = step('reserve', reserved || design ? 'done' : 'current')
  let generate: WorkflowStep
  if (design) generate = step('generate', 'done', null, stale ? 'stale' : null)
  else if (!reserved) generate = step('generate', 'blocked', 'needSku')
  else if (paramsValid === false) generate = step('generate', 'blocked', 'needValid')
  else generate = step('generate', 'current')
  // Render follows the latest generated revision: a render of an older one does not count,
  // and only a finished job is done (queued or running is in progress).
  let render: WorkflowStep
  const warning = stale ? 'rendersSaved' : null
  if (!design) render = step('render', 'blocked', 'needDesign')
  else if (!renderJob) render = step('render', 'current', null, warning)
  else if (renderJob.rev !== design.rev) render = step('render', 'current', null, warning, true)
  else if (renderJob.status === 'done') render = step('render', 'done', null, warning)
  else if (renderJob.status === 'failed') render = step('render', 'failed', null, warning)
  else render = step('render', 'running', null, warning)
  return [reserve, generate, render]
}

