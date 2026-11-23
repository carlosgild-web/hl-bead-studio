import { initialState, type StudioState } from './state'

/**
 * The studio session survives a reload (QA 2026-11-23, item 5): the chat, the panel, the
 * reserved SKU, the design and the open tab are kept in `sessionStorage`, so they last as
 * long as the browser tab. Storage can be missing or full (private windows, blocked site
 * data): every read and write is wrapped, and the studio then simply starts empty.
 */
export const SESSION_KEY = 'hl-bead-studio:session:v1'

/** What is not kept: a turn in flight and an open question belong to the old page. */
function stored(state: StudioState): StudioState {
  return { ...state, busy: false, asking: null }
}

export function saveSession(state: StudioState, storage: Storage | undefined = safeStorage()): void {
  if (!storage) return
  try {
    if (state === initialState) storage.removeItem(SESSION_KEY)
    else storage.setItem(SESSION_KEY, JSON.stringify(stored(state)))
  } catch {
    // Full or blocked storage: the session is just not kept.
  }
}

export function loadSession(storage: Storage | undefined = safeStorage()): StudioState {
  if (!storage) return initialState
  try {
    const raw = storage.getItem(SESSION_KEY)
    if (!raw) return initialState
    const data: unknown = JSON.parse(raw)
    if (!isSession(data)) return initialState
    return stored({ ...initialState, ...data })
  } catch {
    return initialState
  }
}

function isSession(data: unknown): data is Partial<StudioState> {
  if (!data || typeof data !== 'object') return false
  const d = data as Record<string, unknown>
  return (
    Array.isArray(d.items) &&
    typeof d.params === 'object' &&
    d.params !== null &&
    typeof d.actions === 'object' &&
    d.actions !== null &&
    Array.isArray(d.renderJobs)
  )
}

function safeStorage(): Storage | undefined {
  try {
    return typeof window === 'undefined' ? undefined : window.sessionStorage
  } catch {
    return undefined
  }
}
