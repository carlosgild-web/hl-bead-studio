import { useQuery } from '@tanstack/react-query'
import { CheckCircle2, Loader2, TriangleAlert } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { api } from '@/api/client'
import type { FamilyInfo } from '@/api/types'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

import { useDebounced, useLanguage } from './context'
import { fullName } from './state'

/** What to put back in the field for a full name: everything but the family word. */
function typedPart(name: string, suffix: string): string {
  return name.endsWith(` ${suffix}`) ? name.slice(0, -suffix.length - 1) : name
}

/**
 * The product name of the reserve form. The family word is a fixed suffix, so the designer
 * types only the evocative words; below, while typing, the full name, the GEN-03 check
 * against the SAP catalog, a mechanical fix and close names. The check only informs: the
 * card is still checked again on the server, and only Confirm reserves (invariant 2).
 */
export function NameField({
  id,
  family,
  value,
  onChange,
}: {
  id: string
  family: FamilyInfo
  value: string
  onChange: (typed: string) => void
}) {
  const { t } = useTranslation()
  const language = useLanguage()
  const suffix = family.name_suffix
  const name = fullName(value, suffix)
  const typed = value.trim() !== ''
  const debounced = useDebounced(typed ? name : '', 300)
  const check = useQuery({
    queryKey: ['name-check', family.code, debounced],
    queryFn: () => api.checkName(family.code, debounced),
    enabled: debounced !== '',
    staleTime: 30_000,
  })
  const settled = check.data && check.data.name === name
  const hintId = `${id}-hint`
  const statusId = `${id}-status`

  return (
    <div className="grid gap-1.5">
      <div className="flex h-9 items-center rounded-md border border-input shadow-xs focus-within:ring-[3px] focus-within:ring-ring/50">
        <Input
          id={id}
          value={value}
          maxLength={40}
          required
          autoComplete="off"
          placeholder={t('panel.actions.namePlaceholder')}
          aria-describedby={`${hintId} ${statusId}`}
          onChange={(e) => onChange(e.target.value)}
          className="h-full min-w-0 flex-1 border-0 shadow-none focus-visible:ring-0"
        />
        <span className="shrink-0 pr-3 text-sm text-muted-foreground select-none" aria-hidden>
          {suffix}
        </span>
      </div>
      <p id={hintId} className="text-xs text-muted-foreground">
        {t('panel.actions.nameHint', { suffix })}
      </p>

      <div id={statusId} aria-live="polite" className="space-y-1 text-xs">
        {typed && (
          <p>
            <span className="text-muted-foreground">{t('panel.actions.namePreview')}: </span>
            <span className="font-medium">{name}</span>
          </p>
        )}
        {typed && !settled && check.isFetching && (
          <p className="flex items-center gap-1 text-muted-foreground">
            <Loader2 className="size-3 animate-spin" /> {t('panel.actions.nameChecking')}
          </p>
        )}
        {typed && settled && check.data && (
          <>
            {check.data.follows ? (
              <p className="flex items-center gap-1 text-success">
                <CheckCircle2 className="size-3.5" /> {t('panel.actions.nameFree')}
              </p>
            ) : (
              <ul className="space-y-0.5">
                {check.data.violations.map((v, i) => (
                  <li key={i} className="flex items-start gap-1 text-amber-700">
                    <TriangleAlert className="mt-0.5 size-3.5 shrink-0" />
                    <span>
                      <span className="font-mono">{v.rule}</span>{' '}
                      {language === 'es' && v.message_es ? v.message_es : v.message}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            {check.data.suggestion && (
              <p className="flex flex-wrap items-center gap-1.5">
                <span className="text-muted-foreground">{t('panel.actions.nameSuggestion')}</span>
                <button
                  type="button"
                  className="rounded border bg-background px-1.5 py-0.5 font-medium hover:bg-accent"
                  onClick={() => onChange(typedPart(check.data!.suggestion!, suffix))}
                >
                  {check.data.suggestion}
                </button>
              </p>
            )}
            {check.data.similar.length > 0 && (
              <p className="text-muted-foreground">
                {t('panel.actions.nameSimilar')}:{' '}
                {check.data.similar.map((s, i) => (
                  <span key={s.sku}>
                    {i > 0 && ', '}
                    <span className={cn(s.name === name && 'font-semibold')}>{s.name}</span>{' '}
                    <span className="font-mono">({s.sku})</span>
                  </span>
                ))}
              </p>
            )}
            {!check.data.sap_available && <p className="text-muted-foreground">{t('panel.actions.nameNoSap')}</p>}
          </>
        )}
      </div>
    </div>
  )
}
