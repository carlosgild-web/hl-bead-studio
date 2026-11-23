import { ArrowUp, Ban, Check, CheckCircle2, Clock, Loader2, ShieldCheck, XCircle } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { PendingAction } from '@/api/types'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import { cardAnchor, goToCard, useRenderJob, useStudio } from './context'

/**
 * Shown next to a button that opened a card without the assistant (the workflow, "Generate
 * Rev B"): the card is in the chat and waits for Confirm there. Gone once it is decided.
 */
export function CardOpenedNote({ actionId }: { actionId: string | null }) {
  const { t } = useTranslation()
  if (!actionId) return null
  return (
    <p role="status" className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-primary">
      <span>{t('panel.actions.cardOpened')}</span>
      <button type="button" className="inline-flex items-center gap-0.5 font-medium underline underline-offset-2" onClick={() => goToCard(actionId)}>
        {t('panel.actions.goToCard')} <ArrowUp className="size-3" />
      </button>
    </p>
  )
}

/** "Render job #4: rendering", live until the job is done or failed. */
function RenderStatus({ jobId }: { jobId: number }) {
  const { t } = useTranslation()
  const job = useRenderJob(jobId)
  return <>{t('card.done.render', { job_id: jobId, status: t(`renderStatus.${job?.status ?? 'queued'}`) })}</>
}

function Row({ label, value }: { label: string; value: unknown }) {
  if (value === undefined || value === null || value === '') return null
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right font-mono">{String(value)}</dd>
    </div>
  )
}

function isExpired(action: PendingAction): boolean {
  return action.status === 'pending' && new Date(action.expires_at).getTime() < Date.now()
}

/**
 * A confirmation card. The assistant can only open it; the designer's click on Confirm is
 * the one thing that reserves a SKU, writes files or queues a render (invariant 2).
 */
export function ActionCard({ action }: { action: PendingAction }) {
  const { t } = useTranslation()
  const { decide } = useStudio()
  const [working, setWorking] = useState<'confirm' | 'cancel' | null>(null)
  const p = action.payload
  const r = action.result
  const status = isExpired(action) ? 'expired' : action.status
  const open = status === 'pending'

  async function click(decision: 'confirm' | 'cancel') {
    setWorking(decision)
    try {
      await decide(action.id, decision)
    } finally {
      setWorking(null)
    }
  }

  return (
    <article
      id={cardAnchor(action.id)}
      aria-label={t(`card.title.${action.kind}`)}
      data-status={status}
      className={cn(
        'rounded-lg border bg-card p-3 text-sm shadow-sm',
        open && 'border-primary/50 ring-1 ring-primary/20',
        status === 'failed' && 'border-destructive/50',
      )}
    >
      <header className="mb-2 flex items-center gap-2">
        <ShieldCheck className="size-4 text-primary" />
        <h3 className="font-semibold">{t(`card.title.${action.kind}`)}</h3>
        <span className="ml-auto text-xs text-muted-foreground">{t(`card.status.${status}`)}</span>
      </header>

      <dl className="space-y-0.5">
        {action.kind === 'reserve_sku' && (
          <>
            <Row label={t('card.name')} value={p.name} />
            <Row label={t('card.family')} value={p.family} />
            <Row label={t('card.collection')} value={p.collection} />
          </>
        )}
        {action.kind === 'generate_design' && (
          <>
            <Row label="SKU" value={`${String(p.sku)} · Rev ${String(p.rev)}`} />
            <Row label={t('card.name')} value={p.name} />
            <Row label={t('card.family')} value={p.family} />
            <Row label={t('card.sapMaterial')} value={p.sap_material} />
          </>
        )}
        {action.kind === 'render' && (
          <>
            <Row label="SKU" value={`${String(p.sku)} · Rev ${String(p.rev)}`} />
            <Row label={t('card.finish')} value={p.finish} />
          </>
        )}
      </dl>

      {open && (
        <>
          <p className="mt-2 text-xs text-muted-foreground">{t(`card.explain.${action.kind}`)}</p>
          <div className="mt-3 flex gap-2">
            <Button size="sm" data-confirm onClick={() => void click('confirm')} disabled={working !== null}>
              {working === 'confirm' ? <Loader2 className="animate-spin" /> : <Check />}
              {t('card.confirm')}
            </Button>
            <Button size="sm" variant="outline" onClick={() => void click('cancel')} disabled={working !== null}>
              <Ban /> {t('card.cancel')}
            </Button>
          </div>
        </>
      )}

      {status === 'confirmed' && r?.ok && (
        <div className="mt-2 rounded-md bg-success/10 p-2 text-success" role="status">
          <p className="flex items-center gap-1.5 font-medium">
            <CheckCircle2 className="size-4" />{' '}
            {action.kind === 'render' && typeof r.job_id === 'number' ? (
              <RenderStatus jobId={r.job_id} />
            ) : (
              t(`card.done.${action.kind}`, { ...r })
            )}
          </p>
          {action.kind === 'reserve_sku' && (
            <dl className="mt-1 space-y-0.5 text-foreground">
              <Row label="SKU" value={r.sku} />
              <Row label={t('card.sapMaterial')} value={r.sap_material} />
              <Row label={t('card.sapStatus')} value={r.status} />
            </dl>
          )}
          {action.kind === 'generate_design' && r.files && (
            <ul className="mt-1 font-mono text-xs text-foreground">
              {r.files.map((f) => (
                <li key={f}>{f}</li>
              ))}
            </ul>
          )}
        </div>
      )}
      {status === 'failed' && (
        <p className="mt-2 flex items-start gap-1.5 text-destructive" role="alert">
          <XCircle className="mt-0.5 size-4 shrink-0" /> {r?.message}
        </p>
      )}
      {status === 'expired' && (
        <p className="mt-2 flex items-center gap-1.5 text-muted-foreground">
          <Clock className="size-4" /> {t('card.expiredHelp')}
        </p>
      )}
    </article>
  )
}
