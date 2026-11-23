import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { createContext, type Dispatch, useCallback, useContext, useEffect, useState, useSyncExternalStore } from 'react'
import { useTranslation } from 'react-i18next'

import { ApiError, api, renderEventsUrl } from '@/api/client'
import type { Language, OpenCardRequest, Params, RenderJob } from '@/api/types'

import { paramsDiff, paramsKey, type StudioAction, type StudioState } from './state'

export interface StudioContextValue {
  state: StudioState
  dispatch: Dispatch<StudioAction>
  send: (text: string) => Promise<void>
  decide: (actionId: string, decision: 'confirm' | 'cancel') => Promise<void>
}

export const StudioContext = createContext<StudioContextValue | null>(null)

export function useLanguage(): Language {
  const { i18n } = useTranslation()
  return i18n.language === 'es' ? 'es' : 'en'
}

export function useStudio(): StudioContextValue {
  const value = useContext(StudioContext)
  if (!value) throw new Error('useStudio needs a StudioProvider')
  return value
}

export function useDebounced<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(timer)
  }, [value, delayMs])
  return debounced
}

export function useFamilyInfo(code: string | null) {
  const language = useLanguage()
  return useQuery({
    queryKey: ['family', code, language],
    queryFn: () => api.family(code!, language),
    enabled: Boolean(code),
    staleTime: Infinity,
  })
}

/**
 * Live validation and the 3D preview of the panel's parameters. The backend decides
 * validity (invariant 1); the UI only shows the answer.
 */
export function usePanelPreview(family: string | null, params: Params) {
  const key = useDebounced(family && Object.keys(params).length ? paramsKey(params) : null, 350)
  return useQuery({
    queryKey: ['preview', family, key],
    queryFn: () => api.preview(family!, Object.fromEntries(JSON.parse(key!)) as Params),
    enabled: Boolean(family && key),
    placeholderData: keepPreviousData,
    staleTime: Infinity,
    gcTime: 5 * 60_000,
  })
}

/** The reason in the server's refusal of a card: its message plus the rule ids it cites. */
export function refusal(error: unknown): string {
  if (!(error instanceof ApiError)) return error instanceof Error ? error.message : String(error)
  const body = error.body as { result?: { violations?: { rule: string; message: string }[] } }
  const violations = body?.result?.violations ?? []
  return [error.message, ...violations.map((v) => `${v.rule}: ${v.message}`)].join('\n')
}

/** The id of a card's element in the chat, for links that bring the designer to it. */
export const cardAnchor = (actionId: string) => `card-${actionId}`

/** Scroll the chat smoothly to a card and put the focus on its Confirm button. */
export function goToCard(actionId: string) {
  const card = document.getElementById(cardAnchor(actionId))
  card?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' })
  card?.querySelector<HTMLButtonElement>('[data-confirm]')?.focus({ preventScroll: true })
}

export type CardRequest =Omit<OpenCardRequest, 'conversation_id' | 'language'>

/**
 * Open a confirmation card without the assistant (decision 0014): the panel's workflow
 * and the chat's "Next step" chip both use it, with any LLM provider. It only opens the
 * card; the designer's Confirm on it decides (invariant 2).
 */
export function useOpenCard() {
  const { state, dispatch } = useStudio()
  const language = useLanguage()
  const [working, setWorking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [openedId, setOpenedId] = useState<string | null>(null)
  const conversationId = state.conversationId
  const actions = state.actions
  const open = useCallback(
    async (request: CardRequest): Promise<boolean> => {
      setWorking(true)
      setError(null)
      try {
        const opened = await api.openCard({ ...request, conversation_id: conversationId, language })
        const known = opened.action.id in actions
        dispatch({ type: 'event', event: { type: 'conversation', data: { id: opened.conversation_id } } })
        dispatch({ type: 'event', event: { type: 'pending_action', data: { action: opened.action } } })
        setOpenedId(opened.action.id)
        // The card was already in the chat: bring the designer to it.
        if (known) goToCard(opened.action.id)
        return true
      } catch (caught) {
        setError(refusal(caught))
        return false
      } finally {
        setWorking(false)
      }
    },
    [conversationId, language, dispatch, actions],
  )
  // The card this hook opened, while it still waits for the designer's Confirm or Cancel.
  const pendingId = openedId && state.actions[openedId]?.status === 'pending' ? openedId : null
  return { open, working, error, clearError: () => setError(null), pendingId }
}

/**
 * The generated revision of this session against the panel: its record (the Drawing tab's
 * query, cached once), what changed since, and the revision a new generation gets.
 */
export function useDesignStatus() {
  const { state } = useStudio()
  const info = useFamilyInfo(state.family)
  const record = useQuery({
    queryKey: ['design', state.design?.sku, state.design?.rev],
    queryFn: () => api.design(state.design!.sku, state.design!.rev),
    enabled: Boolean(state.design),
  })
  const data = record.data
  const comparable = Boolean(data && data.family === state.family && Object.keys(state.params).length)
  const diff = comparable && data ? paramsDiff(data.params, state.params, info.data?.parameters ?? {}) : []
  return { record: data, diff, stale: diff.length > 0, nextRev: data?.next_rev ?? null }
}

// --- live render jobs ---------------------------------------------------------------------

interface JobFeed {
  job: RenderJob | null
  listeners: Set<() => void>
  source: EventSource | null
}

const feeds = new Map<number, JobFeed>()

/** Tests start each case without the jobs an earlier case followed. */
export function resetRenderJobs(): void {
  feeds.forEach((entry) => entry.source?.close())
  feeds.clear()
}

function feed(jobId: number): JobFeed {
  let entry = feeds.get(jobId)
  if (!entry) {
    entry = { job: null, listeners: new Set(), source: null }
    feeds.set(jobId, entry)
  }
  return entry
}

function subscribeJob(jobId: number, listener: () => void): () => void {
  const entry = feed(jobId)
  entry.listeners.add(listener)
  const finished = entry.job?.status === 'done' || entry.job?.status === 'failed'
  if (!entry.source && !finished) {
    const source = new EventSource(renderEventsUrl(jobId))
    entry.source = source
    source.addEventListener('status', (event) => {
      entry.job = JSON.parse((event as MessageEvent<string>).data) as RenderJob
      if (entry.job.status === 'done' || entry.job.status === 'failed') {
        source.close()
        entry.source = null
      }
      entry.listeners.forEach((fn) => fn())
    })
    source.onerror = () => {
      source.close()
      entry.source = null
    }
  }
  return () => {
    entry.listeners.delete(listener)
    if (entry.listeners.size === 0 && entry.source) {
      entry.source.close()
      entry.source = null
    }
  }
}

/**
 * One render job, followed live over the server's events stream. The stepper, the chat
 * card and the Renders tab share one stream per job; the last status stays known after it
 * closes. `null` until the first event.
 */
export function useRenderJob(jobId: number | null): RenderJob | null {
  const subscribe = useCallback(
    (listener: () => void) => (jobId === null ? () => {} : subscribeJob(jobId, listener)),
    [jobId],
  )
  return useSyncExternalStore(subscribe, () => (jobId === null ? null : (feeds.get(jobId)?.job ?? null)))
}

