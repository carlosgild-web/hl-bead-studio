import { FileBox, ImageIcon, Loader2, Tag } from 'lucide-react'
import { type FormEvent, type ReactNode, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { ApiError, api } from '@/api/client'
import type { ActionKind, FamilyInfo, OpenCardRequest, Validation } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

import { useLanguage, useStudio } from './context'

const NATIVE_SELECT =
  'h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm shadow-xs outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50'

function Labeled({ id, label, children }: { id: string; label: string; children: ReactNode }) {
  return (
    <div className="grid gap-1">
      <label htmlFor={id} className="text-xs font-medium text-muted-foreground">
        {label}
      </label>
      {children}
    </div>
  )
}

/** The reason in the server's refusal: its message plus the rule ids it cites. */
function refusal(error: unknown): string {
  if (!(error instanceof ApiError)) return error instanceof Error ? error.message : String(error)
  const body = error.body as { result?: { violations?: { rule: string; message: string }[] } }
  const violations = body?.result?.violations ?? []
  return [error.message, ...violations.map((v) => `${v.rule}: ${v.message}`)].join('\n')
}

/**
 * "Reserve SKU…", "Generate files…" and "Render…" (decision 0014): open the same
 * confirmation cards the assistant opens, for when the designer does not need the assistant.
 * The backend checks everything again, and only Confirm on the card acts (invariant 2).
 */
export function PanelActions({
  family,
  validation,
}: {
  family: FamilyInfo
  validation?: Validation
}) {
  const { t } = useTranslation()
  const language = useLanguage()
  const { state, dispatch } = useStudio()
  const [open, setOpen] = useState<ActionKind | null>(null)
  const [name, setName] = useState('')
  const [collection, setCollection] = useState('')
  const [sku, setSku] = useState('')
  const [rev, setRev] = useState('A')
  const [working, setWorking] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const option = state.params[family.option_parameter]
  const skuValue = sku || state.reserved?.sku || ''
  const blocked: Record<ActionKind, string | null> = {
    reserve_sku: null,
    generate_design: validation?.valid ? null : t('panel.actions.needValid'),
    render: state.design ? null : t('panel.actions.needDesign'),
  }

  function toggle(kind: ActionKind) {
    setError(null)
    setOpen(open === kind ? null : kind)
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!open) return
    const base = { kind: open, conversation_id: state.conversationId, language }
    let body: OpenCardRequest
    if (open === 'reserve_sku') {
      body = { ...base, family: family.code, name: name.trim(), collection }
    } else if (open === 'generate_design') {
      if (!skuValue) {
        setError(t('panel.actions.needSku'))
        return
      }
      body = { ...base, family: family.code, sku: skuValue.trim().toUpperCase(), rev, params: state.params }
    } else {
      body = { ...base, sku: state.design!.sku, rev: state.design!.rev, finish: String(option ?? '') }
    }
    setWorking(true)
    setError(null)
    try {
      const opened = await api.openCard(body)
      dispatch({ type: 'event', event: { type: 'conversation', data: { id: opened.conversation_id } } })
      dispatch({ type: 'event', event: { type: 'pending_action', data: { action: opened.action } } })
      setOpen(null)
    } catch (caught) {
      setError(refusal(caught))
    } finally {
      setWorking(false)
    }
  }

  const buttons: { kind: ActionKind; icon: ReactNode; label: string; description: string }[] = [
    {
      kind: 'reserve_sku',
      icon: <Tag />,
      label: t('panel.actions.reserve'),
      description: t('panel.actions.reserveDesc'),
    },
    {
      kind: 'generate_design',
      icon: <FileBox />,
      label: t('panel.actions.generate'),
      description: t('panel.actions.generateDesc'),
    },
    {
      kind: 'render',
      icon: <ImageIcon />,
      label: t('panel.actions.render'),
      description: t('panel.actions.renderDesc'),
    },
  ]

  return (
    <section aria-labelledby="panel-actions-title" className="space-y-3 rounded-lg border bg-card p-3 shadow-xs">
      <div>
        <h3 id="panel-actions-title" className="text-sm font-semibold">
          {t('panel.actions.title')}
        </h3>
        <p className="mt-0.5 text-xs text-muted-foreground">{t('panel.actions.hint')}</p>
      </div>
      <ol className="space-y-2">
        {buttons.map((b, index) => {
          const reason = blocked[b.kind]
          const expanded = open === b.kind
          return (
            <li
              key={b.kind}
              className={cn(
                'rounded-md border transition-colors',
                expanded ? 'border-primary/40 bg-muted/40' : 'border-border',
                reason && 'opacity-80',
              )}
            >
              <div className="flex items-start gap-3 p-2.5">
                <span
                  aria-hidden
                  className={cn(
                    'grid size-8 shrink-0 place-items-center rounded-md [&_svg]:size-4',
                    reason ? 'bg-muted text-muted-foreground' : 'bg-primary/10 text-primary',
                  )}
                >
                  {b.icon}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-xs text-muted-foreground">
                    <span className="font-mono">{index + 1}</span> · {b.description}
                  </p>
                  {reason && (
                    <p id={`blocked-${b.kind}`} className="mt-0.5 text-xs text-amber-700">
                      {reason}
                    </p>
                  )}
                </div>
                <Button
                  type="button"
                  size="sm"
                  variant={expanded ? 'default' : 'outline'}
                  aria-expanded={expanded}
                  aria-describedby={reason ? `blocked-${b.kind}` : undefined}
                  disabled={state.busy || reason !== null}
                  onClick={() => toggle(b.kind)}
                  className="shrink-0"
                >
                  {b.label}
                </Button>
              </div>
              {expanded && (
                <form onSubmit={submit} className="grid gap-2 border-t px-2.5 pt-2.5 pb-2.5" aria-label={buttons.find((b) => b.kind === open)?.label}>
                  {open === 'reserve_sku' && (
                    <div className="grid gap-2 sm:grid-cols-[2fr_1fr]">
                      <Labeled id="card-name" label={t('panel.actions.name')}>
                        <Input
                          id="card-name"
                          value={name}
                          maxLength={40}
                          required
                          placeholder={t('panel.actions.namePlaceholder', { suffix: family.name_suffix })}
                          onChange={(e) => setName(e.target.value)}
                        />
                      </Labeled>
                      <Labeled id="card-collection" label={t('panel.actions.collection')}>
                        <select
                          id="card-collection"
                          className={NATIVE_SELECT}
                          value={collection}
                          onChange={(e) => setCollection(e.target.value)}
                        >
                          <option value="">{t('panel.actions.none')}</option>
                          {family.collections.map((c) => (
                            <option key={c} value={c}>
                              {c}
                            </option>
                          ))}
                        </select>
                      </Labeled>
                    </div>
                  )}
                  {open === 'generate_design' && (
                    <div className="grid grid-cols-[2fr_1fr] gap-2">
                      <Labeled id="card-sku" label={t('panel.actions.sku')}>
                        <Input
                          id="card-sku"
                          value={skuValue}
                          maxLength={16}
                          placeholder={family.kind === 'glass_bead' ? 'GB-1034' : 'CH-2034'}
                          onChange={(e) => setSku(e.target.value)}
                          className="font-mono"
                        />
                      </Labeled>
                      <Labeled id="card-rev" label={t('panel.actions.rev')}>
                        <Input
                          id="card-rev"
                          value={rev}
                          maxLength={2}
                          onChange={(e) => setRev(e.target.value.toUpperCase())}
                          className="font-mono"
                        />
                      </Labeled>
                    </div>
                  )}
                  {open === 'render' && state.design && (
                    <p className="text-sm">
                      <span className="font-mono">
                        {state.design.sku} · Rev {state.design.rev}
                      </span>{' '}
                      · {t('panel.actions.finish')}:{' '}
                      {family.swatches.find((s) => s.id === option)?.name ?? String(option ?? '')}
                    </p>
                  )}
                  {error && (
                    <p role="alert" className="text-sm whitespace-pre-line text-destructive">
                      {error}
                    </p>
                  )}
                  <div className="flex gap-2">
                    <Button type="submit" size="sm" disabled={working}>
                      {working && <Loader2 className="animate-spin" />}
                      {t('panel.actions.open')}
                    </Button>
                    <Button type="button" size="sm" variant="ghost" onClick={() => setOpen(null)}>
                      {t('panel.actions.close')}
                    </Button>
                  </div>
                </form>
              )}
            </li>
          )
        })}
      </ol>
    </section>
  )
}
