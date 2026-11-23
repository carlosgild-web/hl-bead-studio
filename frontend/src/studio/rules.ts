import { useQuery } from '@tanstack/react-query'

import { api } from '@/api/client'
import { guide } from '@/demo-guide/guide.config'

import { useLanguage } from './context'

/** The manual on GitHub: `productHref` points at the folder (`tree`); a file is a `blob`. */
const MANUAL_BASE = guide.productHref.replace('/tree/', '/blob/')
export const RULE_ID = /\b((?:GB|CH|GEN)-\d{2})\b/g

/** A rule id's place in the manual, in the UI language; null until known or if absent. */
export function useRuleHref(): (rule: string) => string | null {
  const language = useLanguage()
  const rules = useQuery({ queryKey: ['rules', language], queryFn: () => api.rules(language), staleTime: Infinity })
  return (rule) => {
    const at = rules.data?.[rule]
    return at ? `${MANUAL_BASE}/${language}/${at.file}#${at.anchor}` : null
  }
}
