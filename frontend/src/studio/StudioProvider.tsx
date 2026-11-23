import { useQueryClient } from '@tanstack/react-query'
import { type ReactNode, useCallback, useEffect, useReducer, useRef } from 'react'

import { api, streamChat } from '@/api/client'
import type { ChatEvent, PendingAction, PreviewResponse } from '@/api/types'

import { StudioContext, useLanguage } from './context'
import { loadSession, saveSession } from './persist'
import { paramsKey, studioReducer } from './state'

/** Holds the studio state: the panel, the conversation, the cards and the outputs. */
export function StudioProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(studioReducer, undefined, loadSession)
  const queryClient = useQueryClient()
  const language = useLanguage()
  const stateRef = useRef(state)
  useEffect(() => {
    stateRef.current = state
    saveSession(state)
  }, [state])

  // After a reload, a card that was pending may have been decided or expired since: ask the
  // server once for the current status of each restored pending card.
  useEffect(() => {
    for (const action of Object.values(stateRef.current.actions)) {
      if (action.status !== 'pending') continue
      api
        .action(action.id)
        .then((fresh) => dispatch({ type: 'refreshAction', action: fresh }))
        .catch(() => {
          // Unknown to the server (a reset database): the card's own expiry still applies.
        })
    }
  }, [])

  // The rule edition of the latest proposal: a preview event carries no validation of its own.
  const edition = useRef('')

  const onEvent = useCallback(
    (event: ChatEvent) => {
      if (event.type === 'parameter_proposal') edition.current = event.data.validation.rule_edition
      if (event.type === 'preview') {
        // The assistant built this preview already: the viewer uses it without a rebuild.
        const { family, params } = event.data
        const validation = {
          valid: true,
          family,
          params,
          violations: [],
          notes: [],
          rule_edition: edition.current,
        }
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
      // A step that finished asks the workflow to open the next one (it waits until it can).
      if (action.status === 'confirmed' && action.result?.ok !== false) {
        if (action.kind === 'reserve_sku') dispatch({ type: 'wantStep', step: 'generate' })
        if (action.kind === 'generate_design') dispatch({ type: 'wantStep', step: 'render' })
      }
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

