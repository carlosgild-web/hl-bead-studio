import { Check, FileBox, ImageIcon, Loader2, Tag, TriangleAlert, X } from 'lucide-react'
import { type FormEvent, type ReactNode, useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { ActionKind, FamilyInfo, Validation } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

import { CardOpenedNote } from './ActionCard'
import { type CardRequest, useDesignStatus, useOpenCard, useRenderJob, useStudio } from './context'
import { NameField, type NameStatus } from './NameField'
import { StaleNotice } from './OutputTabs'
import { fullName, type StepId, workflowSteps } from './state'

const NATIVE_SELECT =
  'h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm shadow-xs outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50'

const KIND: Record<StepId, ActionKind> = {
  reserve: 'reserve_sku',
  generate: 'generate_design',
  render: 'render',
}

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

/**
 * The design flow as a stepper (decision 0014): reserve a SKU, generate the files, render.
 * Each step opens the same confirmation card the assistant opens; only Confirm on the card
 * acts (invariant 2). Step states come from what the studio has (confirmed cards, from here
 * or from the assistant), so they stay right whichever way the work was done.
 */
export function PanelActions({ family, validation }: { family: FamilyInfo; validation?: Validation }) {
  const { t } = useTranslation()
  const { state } = useStudio()
  const { open: openCard, working, error: openError, clearError, pendingId } = useOpenCard()
  const design = useDesignStatus()
  const latestJobId = state.renderJobs[0] ?? null
  const job = useRenderJob(latestJobId)
  // The job's revision is known from its confirmed card before the first live event.
  const renderCard = Object.values(state.actions).find((a) => a.kind === 'render' && a.result?.job_id === latestJobId)
  const jobRev = job?.rev ?? (renderCard ? String(renderCard.payload.rev) : (state.design?.rev ?? ''))
  const steps = workflowSteps({
    reserved: state.reserved,
    design: state.design,
    renderJob: latestJobId === null ? null : { id: latestJobId, status: job?.status ?? 'queued', rev: jobRev },
    paramsValid: validation?.valid,
    stale: design.stale,
  })
  const olderRender = steps[2].olderRender

  const [form, setForm] = useState<StepId | null>(null)
  const [name, setName] = useState('')
  const [nameStatus, setNameStatus] = useState<NameStatus>('empty')
  const [collection, setCollection] = useState('')
  const [sku, setSku] = useState('')
  const [rev, setRev] = useState('A')
  const [localError, setLocalError] = useState<string | null>(null)
  const error = localError ?? openError
  const option = state.params[family.option_parameter]

  function show(step: StepId, existingSku = false) {
    clearError()
    setLocalError(null)
    if (step === 'generate') {
      setSku(existingSku ? '' : (state.design?.sku ?? state.reserved?.sku ?? ''))
      setRev(state.design ? (design.nextRev ?? '') : 'A')
    }
    setForm(form === step && !existingSku ? null : step)
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!form) return
    let request: CardRequest
    if (form === 'reserve') {
      request = { kind: 'reserve_sku', family: family.code, name: fullName(name, family.name_suffix), collection }
    } else if (form === 'generate') {
      if (!sku.trim()) {
        setLocalError(t('panel.actions.needSku'))
        return
      }
      request = { kind: 'generate_design', family: family.code, sku: sku.trim().toUpperCase(), rev, params: state.params }
    } else {
      request = { kind: 'render', sku: state.design!.sku, rev: state.design!.rev, finish: String(option ?? '') }
    }
    setLocalError(null)
    if (await openCard(request)) setForm(null)
  }

  const meta: Record<StepId, { icon: ReactNode; title: string; action: string; description: string }> = {
    reserve: {
      icon: <Tag />,
      title: t('panel.actions.stepReserve'),
      action: t('panel.actions.reserve'),
      description: t('panel.actions.reserveDesc'),
    },
    generate: {
      icon: <FileBox />,
      title: t('panel.actions.stepGenerate'),
      action: t('panel.actions.generate'),
      description: t('panel.actions.generateDesc'),
    },
    render: {
      icon: <ImageIcon />,
      title: t('panel.actions.stepRender'),
      action: t('panel.actions.render'),
      description: t('panel.actions.renderDesc'),
    },
  }

  function summary(step: StepId): string | null {
    if (step === 'reserve') {
      if (state.reserved) return t('panel.actions.doneReserve', { sku: state.reserved.sku, name: state.reserved.name ?? '' })
      return state.design ? t('panel.actions.doneExisting', { sku: state.design.sku }) : null
    }
    if (step === 'generate') return state.design ? t('panel.actions.doneGenerate', { rev: state.design.rev }) : null
    if (latestJobId === null) return null
    if (olderRender) return t('panel.actions.lastRender', { rev: jobRev, id: latestJobId, current: state.design?.rev })
    if (job?.status === 'failed') return t('panel.actions.renderFailed', { id: latestJobId, error: job.error ?? '' })
    return t('panel.actions.doneRender', { id: latestJobId, status: t(`renderStatus.${job?.status ?? 'queued'}`) })
  }

  const statusLabel = {
    current: 'panel.actions.statusCurrent',
    done: 'panel.actions.statusDone',
    blocked: 'panel.actions.statusBlocked',
    running: 'panel.actions.statusRunning',
    failed: 'panel.actions.statusFailed',
  } as const

  const submitDisabled = working || (form === 'reserve' && nameStatus !== 'ok')

  return (
    <section aria-labelledby="panel-actions-title" className="space-y-3 rounded-lg border bg-card p-3 shadow-xs">
      <div>
        <h3 id="panel-actions-title" className="text-sm font-semibold">
          {t('panel.actions.title')}
        </h3>
        <p className="mt-0.5 text-xs text-muted-foreground">{t('panel.actions.hint')}</p>
      </div>
      <ol className="space-y-0">
        {steps.map((step, index) => {
          const m = meta[step.id]
          const done = step.status === 'done'
          const blocked = step.status === 'blocked'
          const current = step.status === 'current'
          const running = step.status === 'running'
          const failed = step.status === 'failed'
          const outdated = done && step.warning === 'stale'
          const expanded = form === step.id
          const reasonId = `blocked-${KIND[step.id]}`
          const line = summary(step.id)
          return (
            <li key={step.id} className="relative flex gap-3 pb-3 last:pb-0" data-step={step.id} data-status={step.status}>
              {index < steps.length - 1 && (
                <span aria-hidden className={cn('absolute top-8 bottom-0 left-[0.9375rem] w-px', done ? 'bg-success/50' : 'bg-border')} />
              )}
              <span
                aria-hidden
                className={cn(
                  'relative z-10 grid size-8 shrink-0 place-items-center rounded-full border text-xs font-semibold',
                  done && !outdated && 'border-success bg-success text-white',
                  outdated && 'border-amber-500 bg-amber-100 text-amber-700',
                  (current || running) && 'border-primary bg-primary/10 text-primary',
                  failed && 'border-destructive bg-destructive/10 text-destructive',
                  blocked && 'border-border bg-muted text-muted-foreground',
                )}
              >
                {outdated ? (
                  <TriangleAlert className="size-4" />
                ) : done ? (
                  <Check className="size-4" />
                ) : running ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : failed ? (
                  <X className="size-4" />
                ) : (
                  index + 1
                )}
              </span>
              <div className={cn('min-w-0 flex-1 rounded-md', expanded && 'bg-muted/40')}>
                <div className="flex items-start gap-2 pt-1">
                  <div className="min-w-0 flex-1">
                    <p className={cn('text-sm font-medium', blocked && 'text-muted-foreground')}>
                      {m.title}
                      <span className="sr-only">
                        {' · '}
                        {t(outdated ? 'panel.actions.statusStale' : statusLabel[step.status])}
                      </span>
                    </p>
                    {line && (
                      <p
                        className={cn(
                          'text-xs',
                          done && !outdated && 'text-success',
                          outdated && 'text-amber-700',
                          failed && 'text-destructive',
                          (current || running) && 'text-muted-foreground',
                        )}
                      >
                        {done && !outdated && '✓ '}
                        {line}
                      </p>
                    )}
                    {current && !line && <p className="text-xs text-muted-foreground">{m.description}</p>}
                    {step.reason && (
                      <p id={reasonId} className="text-xs text-amber-700">
                        {t(`panel.actions.${step.reason}`)}
                      </p>
                    )}
                    {step.warning === 'rendersSaved' && state.design && (
                      <p className="flex items-start gap-1 text-xs text-amber-700">
                        <TriangleAlert className="mt-0.5 size-3.5 shrink-0" />
                        {t('panel.actions.rendersSaved', { rev: state.design.rev })}
                      </p>
                    )}
                    {step.id === 'generate' && step.reason === 'needSku' && (
                      <button
                        type="button"
                        className="mt-0.5 text-xs font-medium text-primary underline-offset-2 hover:underline"
                        onClick={() => show('generate', true)}
                      >
                        {t('panel.actions.useExisting')}
                      </button>
                    )}
                  </div>
                  {running ? null : done || failed ? (
                    step.id !== 'reserve' && (
                      <button
                        type="button"
                        className="shrink-0 pt-0.5 text-xs font-medium text-primary underline-offset-2 hover:underline disabled:opacity-50"
                        disabled={state.busy || (step.id === 'generate' && validation?.valid === false)}
                        onClick={() => show(step.id)}
                      >
                        {t(step.id === 'generate' ? 'panel.actions.redoGenerate' : 'panel.actions.redoRender')}
                      </button>
                    )
                  ) : (
                    <Button
                      type="button"
                      size="sm"
                      variant={expanded ? 'default' : 'outline'}
                      aria-expanded={expanded}
                      aria-describedby={step.reason ? reasonId : undefined}
                      disabled={state.busy || blocked}
                      onClick={() => show(step.id)}
                      className="shrink-0"
                    >
                      {m.action}
                    </Button>
                  )}
                </div>
                {step.id === 'generate' && step.warning === 'stale' && !expanded && <StaleNotice compact />}
                {!expanded && pendingId && state.actions[pendingId]?.kind === KIND[step.id] && (
                  <div className="mt-1">
                    <CardOpenedNote actionId={pendingId} />
                  </div>
                )}

                {expanded && (
                  <form onSubmit={submit} className="mt-2 grid gap-2 border-t px-2.5 pt-2.5 pb-2.5" aria-label={m.action}>
                    {form === 'reserve' && (
                      <div className="grid items-start gap-2 sm:grid-cols-[2fr_1fr]">
                        <Labeled id="card-name" label={t('panel.actions.name')}>
                          <NameField id="card-name" family={family} value={name} onChange={setName} onStatus={setNameStatus} />
                        </Labeled>
                        <Labeled id="card-collection" label={t('panel.actions.collection')}>
                          <select id="card-collection" className={NATIVE_SELECT} value={collection} onChange={(e) => setCollection(e.target.value)}>
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
                    {form === 'generate' && (
                      <div className="grid grid-cols-[2fr_1fr] gap-2">
                        <Labeled id="card-sku" label={t('panel.actions.sku')}>
                          <Input
                            id="card-sku"
                            value={sku}
                            maxLength={16}
                            placeholder={family.kind === 'glass_bead' ? 'GB-1034' : 'CH-2034'}
                            onChange={(e) => setSku(e.target.value)}
                            className="font-mono"
                          />
                        </Labeled>
                        <Labeled id="card-rev" label={t('panel.actions.rev')}>
                          <Input id="card-rev" value={rev} maxLength={2} onChange={(e) => setRev(e.target.value.toUpperCase())} className="font-mono" />
                        </Labeled>
                      </div>
                    )}
                    {form === 'render' && state.design && (
                      <p className="text-sm">
                        <span className="font-mono">
                          {state.design.sku} · Rev {state.design.rev}
                        </span>{' '}
                        · {t('panel.actions.finish')}: {family.swatches.find((s) => s.id === option)?.name ?? String(option ?? '')}
                      </p>
                    )}
                    {error && (
                      <p role="alert" className="text-sm whitespace-pre-line text-destructive">
                        {error}
                      </p>
                    )}
                    <div className="flex gap-2">
                      <Button type="submit" size="sm" disabled={submitDisabled}>
                        {working && <Loader2 className="animate-spin" />}
                        {t('panel.actions.open')}
                      </Button>
                      <Button type="button" size="sm" variant="ghost" onClick={() => setForm(null)}>
                        {t('panel.actions.close')}
                      </Button>
                    </div>
                  </form>
                )}
              </div>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
