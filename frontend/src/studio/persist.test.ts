import { describe, expect, it } from 'vitest'

import { loadSession, saveSession, SESSION_KEY } from './persist'
import { initialState, studioReducer, type StudioState } from './state'

function memoryStorage(): Storage {
  const data = new Map<string, string>()
  return {
    get length() {
      return data.size
    },
    clear: () => data.clear(),
    getItem: (key) => data.get(key) ?? null,
    key: (index) => [...data.keys()][index] ?? null,
    removeItem: (key) => void data.delete(key),
    setItem: (key, value) => void data.set(key, value),
  }
}

const session: StudioState = {
  ...initialState,
  family: 'FAC',
  params: { diameter_mm: 10, color: 'amber' },
  conversationId: 'c1',
  items: [{ kind: 'user', text: 'A 10 mm faceted amber bead' }],
  reserved: { sku: 'GB-1040', name: 'Amber Glow Faceted' },
  design: { sku: 'GB-1040', rev: 'A' },
  tab: 'renders',
  busy: true,
  asking: 'reset',
}

describe('session persistence', () => {
  it('restores the chat, the panel, the SKU and the tab after a reload', () => {
    const storage = memoryStorage()
    saveSession(session, storage)
    const restored = loadSession(storage)
    expect(restored.items).toEqual(session.items)
    expect(restored.params).toEqual(session.params)
    expect(restored.reserved?.sku).toBe('GB-1040')
    expect(restored.design).toEqual({ sku: 'GB-1040', rev: 'A' })
    expect(restored.tab).toBe('renders')
  })

  it('never restores a turn in flight or an open question', () => {
    const storage = memoryStorage()
    saveSession(session, storage)
    const restored = loadSession(storage)
    expect(restored.busy).toBe(false)
    expect(restored.asking).toBeNull()
  })

  it('starts empty on missing, broken or foreign data', () => {
    const storage = memoryStorage()
    expect(loadSession(storage)).toBe(initialState)
    storage.setItem(SESSION_KEY, '{not json')
    expect(loadSession(storage)).toBe(initialState)
    storage.setItem(SESSION_KEY, JSON.stringify({ items: 'nope' }))
    expect(loadSession(storage)).toBe(initialState)
  })

  it('forgets the session on "Start over"', () => {
    const storage = memoryStorage()
    saveSession(session, storage)
    saveSession(studioReducer(session, { type: 'reset' }), storage)
    expect(storage.getItem(SESSION_KEY)).toBeNull()
  })

  it('survives storage that throws', () => {
    const broken = { ...memoryStorage(), setItem: () => { throw new Error('full') }, getItem: () => { throw new Error('blocked') } }
    expect(() => saveSession(session, broken)).not.toThrow()
    expect(loadSession(broken)).toBe(initialState)
  })
})
