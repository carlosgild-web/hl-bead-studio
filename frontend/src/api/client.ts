import type {
  ActionKind,
  CatalogItem,
  ChatEvent,
  DesignRecord,
  FamilyInfo,
  FamilySummary,
  GalleryRender,
  Health,
  Language,
  NameCheck,
  OpenCardRequest,
  Params,
  PendingAction,
  PreviewResponse,
  RenderJob,
  Validation,
} from './types'

/** An HTTP error with the backend's `detail` when it sent one. */
export class ApiError extends Error {
  readonly status: number
  readonly body: unknown

  constructor(status: number, message: string, body: unknown) {
    super(message)
    this.status = status
    this.body = body
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  const text = await response.text()
  let body: unknown = undefined
  try {
    body = text ? JSON.parse(text) : undefined
  } catch {
    body = text
  }
  if (!response.ok) {
    const detail =
      body && typeof body === 'object' && 'detail' in body ? String(body.detail) : undefined
    throw new ApiError(response.status, detail ?? `HTTP ${response.status}`, body)
  }
  return body as T
}

function post<T>(url: string, body?: unknown): Promise<T> {
  return request<T>(url, {
    method: 'POST',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

export const api = {
  health: () => request<Health>('/api/health'),
  families: (lang: Language) => request<FamilySummary[]>(`/api/families?lang=${lang}`),
  family: (code: string, lang: Language) =>
    request<FamilyInfo>(`/api/families/${encodeURIComponent(code)}?lang=${lang}`),
  validate: (family: string, params: Params) =>
    post<Validation>('/api/validate', { family, params }),
  preview: (family: string, params: Params) =>
    post<PreviewResponse>('/api/preview', { family, params }),
  catalog: () => request<CatalogItem[]>('/api/catalog'),
  /** The reserve form's live GEN-03 check (read only). */
  checkName: (family: string, name: string) => post<NameCheck>('/api/names/check', { family, name }),
  design: (sku: string, rev: string) =>
    request<DesignRecord>(`/api/designs/${encodeURIComponent(sku)}/${encodeURIComponent(rev)}`),
  designRenders: (sku: string, rev: string) =>
    request<RenderJob[]>(
      `/api/designs/${encodeURIComponent(sku)}/${encodeURIComponent(rev)}/renders`,
    ),
  gallery: () => request<{ generated_at: string | null; renders: GalleryRender[] }>('/api/gallery'),
  renderJob: (id: number) => request<RenderJob>(`/api/renders/${id}`),
  /**
   * The designer's click on a confirmation card: the only way anything is reserved, written
   * or queued (invariant 2). Failures (422, 409, 410, 502) still carry the action.
   */
  confirm: async (id: string): Promise<PendingAction> => decided(`/api/actions/${id}/confirm`),
  cancel: async (id: string): Promise<PendingAction> => decided(`/api/actions/${id}/cancel`),
  /** Opens a card only; the designer's Confirm still decides (invariant 2). */
  openCard: (body: OpenCardRequest) =>
    post<{ conversation_id: string; action: PendingAction }>('/api/actions', body),
}

async function decided(url: string): Promise<PendingAction> {
  try {
    return await post<PendingAction>(url)
  } catch (error) {
    if (error instanceof ApiError && error.body && typeof error.body === 'object') {
      const body = error.body as Record<string, unknown>
      if ('action' in body) return body.action as PendingAction
      if ('kind' in body && 'status' in body) return body as unknown as PendingAction
    }
    throw error
  }
}

export const renderImageUrl = (jobId: number) => `/api/renders/${jobId}/image`
export const renderEventsUrl = (jobId: number) => `/api/renders/${jobId}/events`

/** Parse a block of server-sent events text into events (the incomplete tail is returned). */
export function parseSse(buffer: string): { events: ChatEvent[]; rest: string } {
  const events: ChatEvent[] = []
  const normalized = buffer.replace(/\r\n/g, '\n')
  const blocks = normalized.split('\n\n')
  const rest = blocks.pop() ?? ''
  for (const block of blocks) {
    let type: string | undefined
    const data: string[] = []
    for (const line of block.split('\n')) {
      if (line.startsWith('event: ')) type = line.slice(7)
      else if (line.startsWith('data: ')) data.push(line.slice(6))
    }
    if (!type || data.length === 0) continue
    try {
      events.push({ type, data: JSON.parse(data.join('\n')) } as ChatEvent)
    } catch {
      // A malformed event is skipped; the stream goes on.
    }
  }
  return { events, rest }
}

export interface ChatRequest {
  message: string
  conversation_id?: string | null
  language: Language
  panel?: { family: string; params: Params } | null
}

/** `POST /api/chat`: one assistant turn, streamed. Calls `onEvent` for each event. */
export async function streamChat(
  body: ChatRequest,
  onEvent: (event: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  if (!response.ok || !response.body) {
    // A refusal (rate limit, daily token cap, unknown conversation) says why in `detail`.
    const text = await response.text()
    let detail = `HTTP ${response.status}`
    try {
      const parsed: unknown = JSON.parse(text)
      if (parsed && typeof parsed === 'object' && 'detail' in parsed) detail = String(parsed.detail)
    } catch {
      // not JSON: keep the status
    }
    throw new ApiError(response.status, detail, text)
  }
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    const { events, rest } = parseSse(buffer)
    buffer = rest
    events.forEach(onEvent)
  }
  const { events } = parseSse(buffer + '\n\n')
  events.forEach(onEvent)
}

export const ACTION_KINDS: ActionKind[] = ['reserve_sku', 'generate_design', 'render']
