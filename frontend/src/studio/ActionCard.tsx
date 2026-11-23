import { ArrowUp, Ban, Check, CheckCircle2, Clock, Loader2, MessageSquare, ShieldCheck, TriangleAlert, XCircle } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { ParamValue, PendingAction } from '@/api/types'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import { cardAnchor, focusChatInput, goToCard, useFamilyInfo, usePanelPreview, useRenderJob, useStudio, useSwatchName } from './context'
import { displayValue } from './display'
import { isExpired } from './state'

/**
 * Shown next to a button that opened a card without the assistant (the workflow, "Generate
 * Rev B"): the card is in the chat and waits for Confirm there. Gone once it is decided.
 */
export function CardOpenedNote({ actionId }: { actionId: string | null }) {
  const { t } = useTranslation()
  const { dispatch } = useStudio()
  if (!actionId) return null
  return (
    <p role="status" className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-primary">
      <span>{t('panel.actions.cardOpened')}</span>
      <button type="button" className="inline-flex items-center gap-0.5 font-medium underline underline-offset-2" onClick={() => {
          // A card set aside with "Use the chat" is in focus again.
          dispatch({ type: 'refocus', actionId })
          goToCard(actionId)
        }}
      >
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

/** The parameters a Generate card lists, in this order, when the family has them. */
const KEY_PARAMS = ['diameter_mm', 'height_mm', 'hole_mm', 'color', 'finish', 'letter', 'engraving_text', 'icon']

function paramsOf(payload: Record<string, unknown>): Record<string, ParamValue> | null {
  const params = payload.params
  return params && typeof params === 'object' ? (params as Record<string, ParamValue>) : null
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

/**
 * A confirmation card. The assistant can only open it; the designer's click on Confirm is
 * the one thing that reserves a SKU, writes files or queues a render (invariant 2).
 * `focused`: the studio is dimmed around it (focus mode); "Use the chat" or Esc sets it aside.
 */
export function ActionCard({ action, focused = false }: { action: PendingAction; focused?: boolean }) {
  const { t } = useTranslation()
  const swatchName = useSwatchName()
  const { state, decide, dispatch } = useStudio()
  const familyInfo = useFamilyInfo(typeof action.payload.family === 'string' ? action.payload.family : null)
  // The panel's own check (cached, no extra request): a reservation while the design breaks
  // rules is allowed, but the card says so (QA 2026-11-23, item 13; decision 0025).
  const panel = usePanelPreview(action.kind === 'reserve_sku' ? state.family : null, state.params)
  const broken =
    action.kind === 'reserve_sku' && panel.data && !panel.data.validation.valid
      ? [...new Set(panel.data.validation.violations.map((v) => v.rule))]
      : []
  // "Use the chat": the card stays pending, set aside, and the designer can ask first.
  const goToChat = () => {
    dispatch({ type: 'dismiss', actionId: action.id })
    focusChatInput()
  }
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
      data-focused={focused || undefined}
      onKeyDown={(e) => {
        if (focused && e.key === 'Escape') goToChat()
      }}
      className={cn(
        'rounded-lg border bg-card p-3 text-sm shadow-sm transition-shadow',
        open && 'border-primary/50 ring-1 ring-primary/20',
        focused && 'shadow-lg ring-2 ring-primary/60',
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
            {open && broken.length > 0 && (
              <p role="note" className="mt-1 flex items-start gap-1.5 rounded-md border border-brand-amber/50 bg-brand-amber/10 px-2 py-1 text-xs">
                <TriangleAlert className="mt-0.5 size-3.5 shrink-0" />
                {t('card.brokenRules', { rules: broken.join(', ') })}
              </p>
            )}
          </>
        )}
        {action.kind === 'generate_design' && (
          <>
            <Row label="SKU" value={`${String(p.sku)} · Rev ${String(p.rev)}`} />
            <Row label={t('card.name')} value={p.name} />
            <Row label={t('card.family')} value={p.family} />
            <Row label={t('card.sapMaterial')} value={p.sap_material} />
            {/* What will be built, so the click confirms a design, not only a SKU. */}
            {familyInfo.data &&
              KEY_PARAMS.filter((k) => k in (paramsOf(p) ?? {}) && familyInfo.data!.parameters[k]).map((k) => (
                <Row
                  key={k}
                  label={familyInfo.data!.parameters[k].label}
                  value={
                    k === familyInfo.data!.option_parameter
                      ? swatchName(String(paramsOf(p)![k]))
                      : displayValue(familyInfo.data!.parameters[k], paramsOf(p)![k], t)
                  }
                />
              ))}
          </>
        )}
        {action.kind === 'render' && (
          <>
            <Row label="SKU" value={`${String(p.sku)} · Rev ${String(p.rev)}`} />
            <Row label={t('card.finish')} value={swatchName(String(p.finish ?? ''))} />
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
            {focused && (
              <Button size="sm" variant="ghost" className="ml-auto" onClick={goToChat} disabled={working !== null}>
                <MessageSquare /> {t('card.useChat')}
              </Button>
            )}
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
