import { useQueryClient } from '@tanstack/react-query'
import { type ReactNode, useCallback, useEffect, useReducer, useRef } from 'react'

import { api, streamChat } from '@/api/client'
import type { ChatEvent, PendingAction, PreviewResponse } from '@/api/types'

import { StudioContext, useLanguage } from './context'
import { initialState, paramsKey, studioReducer } from './state'

/** Holds the studio state: the panel, the conversation, the cards and the outputs. */
export function StudioProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(studioReducer, initialState)
  const queryClient = useQueryClient()
  const language = useLanguage()
  const stateRef = useRef(state)
  useEffect(() => {
    stateRef.current = state
  }, [state])

  const onEvent = useCallback(
    (event: ChatEvent) => {
      if (event.type === 'preview') {
        // The assistant built this preview already: the viewer uses it without a rebuild.
        const { family, params } = event.data
        const validation = { valid: true, family, params, violations: [], notes: [], rule_edition: '' }
        queryClient.setQueryData<PreviewResponse>(['preview', family, paramsKey(params)], {
          validation,
          preview: event.data,
        })
      }
      dispatch({ type: 'event', event })
    },
    [queryClient],
  )

  const send = useCallback(
    async (text: string) => {
      const current = stateRef.current
      if (current.busy || !text.trim()) return
      dispatch({ type: 'send', text })
      const panel = current.family ? { family: current.family, params: current.params } : null
      try {
        await streamChat(
          { message: text, conversation_id: current.conversationId, language, panel },
          onEvent,
        )
      } catch (error) {
        dispatch({ type: 'failed', text: error instanceof Error ? error.message : String(error) })
        return
      }
      // A stream that ended without `done` must not leave the chat locked.
      if (stateRef.current.busy) dispatch({ type: 'event', event: { type: 'done', data: { status: 'ended' } } })
    },
    [language, onEvent],
  )

  const decide = useCallback(
    async (actionId: string, decision: 'confirm' | 'cancel') => {
      let action: PendingAction
      try {
        action = decision === 'confirm' ? await api.confirm(actionId) : await api.cancel(actionId)
      } catch (error) {
        dispatch({ type: 'failed', text: error instanceof Error ? error.message : String(error) })
        return
      }
      dispatch({ type: 'decided', action })
      if (action.kind === 'reserve_sku' || action.kind === 'generate_design') {
        void queryClient.invalidateQueries({ queryKey: ['catalog'] })
      }
    },
    [queryClient],
  )

  return (
    <StudioContext.Provider value={{ state, dispatch, send, decide }}>
      {children}
    </StudioContext.Provider>
  )
}

