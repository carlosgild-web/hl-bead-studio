import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { createContext, type Dispatch, useContext, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { api } from '@/api/client'
import type { Language, Params } from '@/api/types'

import { paramsKey, type StudioAction, type StudioState } from './state'

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
