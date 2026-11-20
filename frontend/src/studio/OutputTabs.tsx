import { useQuery } from '@tanstack/react-query'
import { Download, FileText, ImageIcon, Loader2, RotateCcw, TriangleAlert } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { api, renderImageUrl } from '@/api/client'
import type { ParamValue } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'

import { CardOpenedNote } from './ActionCard'
import { useDesignStatus, useLanguage, useOpenCard, useRenderJob, useStudio } from './context'

function shown(value: ParamValue | undefined): string {
  if (value === undefined) return '—'
  if (typeof value === 'boolean') return value ? '✓' : '✗'
  return String(value)
}

/**
 * The panel no longer matches the generated revision: what changed (with the panel's
 * labels), "Generate Rev B" (opens the card; only Confirm writes, and existing revisions are
 * never overwritten) and "Revert" (puts the saved parameters back in the panel).
 */
export function StaleNotice({ compact = false }: { compact?: boolean }) {
  const { t } = useTranslation()
  const { state, dispatch } = useStudio()
  const { record, diff, stale, nextRev } = useDesignStatus()
  const { open, working, error, pendingId } = useOpenCard()
  if (!stale || !record) return null
  const changes = diff.map((c) => `${c.label} ${shown(c.old)} → ${shown(c.new)}${c.unit && typeof c.new === 'number' ? ` ${c.unit}` : ''}`)
  return (
    <div
      role="status"
      aria-label={t('outputs.stale.title', { rev: record.rev })}
      className={cn('rounded-md border border-amber-300 bg-amber-50 text-amber-900', compact ? 'mt-2 space-y-1.5 p-2 text-xs' : 'space-y-2 p-3 text-sm')}
    >
      <p className="flex items-start gap-1.5">
        <TriangleAlert className={cn('mt-0.5 shrink-0', compact ? 'size-3.5' : 'size-4')} />
        <span>
          <span className="font-semibold">{t('outputs.stale.title', { rev: record.rev })}</span>
          {': '}
          {changes.join('; ')}. {t('outputs.stale.body')}
        </span>
      </p>
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          size="sm"
          disabled={working || !nextRev || state.busy}
          onClick={() =>
            void open({ kind: 'generate_design', family: record.family, sku: record.sku, rev: nextRev!, params: state.params })
          }
        >
          {working && <Loader2 className="animate-spin" />}
          {t('outputs.stale.generate', { rev: nextRev })}
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={() => dispatch({ type: 'setParams', params: record.params })}>
          <RotateCcw /> {t('outputs.stale.revert', { rev: record.rev })}
        </Button>
      </div>
      <CardOpenedNote actionId={pendingId} />
      {error && <p className="whitespace-pre-line text-destructive">{error}</p>}
    </div>
  )
}

function DrawingTab() {
  const { t } = useTranslation()
  const { state } = useStudio()
  const design = useQuery({
    queryKey: ['design', state.design?.sku, state.design?.rev],
    queryFn: () => api.design(state.design!.sku, state.design!.rev),
    enabled: Boolean(state.design),
  })
  if (!state.design) {
    return <p className="p-4 text-sm text-muted-foreground">{t('outputs.noDesign')}</p>
  }
  if (!design.data) {
    return <Loader2 className="m-4 size-5 animate-spin text-muted-foreground" />
  }
  const d = design.data
  return (
    <div className="space-y-3">
      <StaleNotice />
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Badge className="font-mono">
          {d.sku} · Rev {d.rev}
        </Badge>
        <span className="font-medium">{d.name}</span>
        <span className="text-muted-foreground">
          {t('outputs.scale', { scale: d.drawing_scale })} · {d.measurements.mass_g.toFixed(3)} g
        </span>
        <span className="ml-auto flex gap-1.5">
          {(['step', 'stl', 'glb'] as const).map((kind) => (
            <a
              key={kind}
              href={d.urls[kind]}
              className="inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-medium uppercase hover:bg-accent"
            >
              <Download className="size-3" /> {kind}
            </a>
          ))}
        </span>
      </div>
      <iframe
        title={t('outputs.drawingTitle', { sku: d.sku, rev: d.rev })}
        src={d.urls.drawing}
        className="h-[32rem] w-full rounded-md border bg-white"
      />
    </div>
  )
}

/**
 * One render job, followed live (one shared events stream per job) until it is done or
 * failed. A render of an older revision of the generated SKU says so.
 */
export function RenderProgress({ jobId }: { jobId: number }) {
  const { t } = useTranslation()
  const { state } = useStudio()
  const job = useRenderJob(jobId)
  const older = job && state.design && job.sku === state.design.sku && job.rev !== state.design.rev

  const status = job?.status ?? 'queued'
  return (
    <div className="space-y-2 rounded-md border p-3" aria-label={t('outputs.renderJob', { id: jobId })}>
      <div className="flex items-center gap-2 text-sm">
        {(status === 'queued' || status === 'running') && <Loader2 className="size-4 animate-spin" />}
        <span className="font-medium">
          {t('outputs.renderJob', { id: jobId })}
          {job && ` · ${job.sku} Rev ${job.rev} · ${job.finish}`}
        </span>
        {older && (
          <Badge variant="secondary" className="font-normal">
            {t('outputs.olderRevision', { rev: job.rev })}
          </Badge>
        )}
        <Badge variant={status === 'failed' ? 'destructive' : status === 'done' ? 'default' : 'secondary'}>
          {t(`renderStatus.${status}`)}
        </Badge>
        {job?.duration_s != null && (
          <span className="text-xs text-muted-foreground">{job.duration_s.toFixed(0)} s</span>
        )}
      </div>
      {status === 'running' && (
        <div className="h-1.5 overflow-hidden rounded bg-muted">
          <div className="h-full w-1/3 animate-[pulse_1.5s_ease-in-out_infinite] rounded bg-primary" />
        </div>
      )}
      {status === 'failed' && <p className="text-sm text-destructive">{job?.error}</p>}
      {status === 'done' && (
        <img
          src={renderImageUrl(jobId)}
          alt={t('outputs.renderAlt', { sku: job?.sku, finish: job?.finish })}
          className="mx-auto max-h-96 rounded-md"
        />
      )}
    </div>
  )
}

export function Gallery() {
  const { t } = useTranslation()
  const language = useLanguage()
  const gallery = useQuery({ queryKey: ['gallery'], queryFn: api.gallery, staleTime: Infinity })
  if (!gallery.data?.renders.length) return null
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold">{t('outputs.gallery')}</h3>
      <p className="text-xs text-muted-foreground">{t('outputs.galleryNote')}</p>
      <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3 2xl:grid-cols-6">
        {gallery.data.renders.map((r) => (
          <li key={r.file} className="overflow-hidden rounded-md border bg-card">
            <img src={r.url} alt={`${r.name}, ${r.finish_name[language]}`} loading="lazy" className="aspect-square w-full object-cover" />
            <p className="px-2 py-1 text-xs">
              <span className="font-mono">{r.sku}</span> · {r.finish_name[language]}
            </p>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function OutputTabs() {
  const { t } = useTranslation()
  const { state, dispatch } = useStudio()
  const { stale } = useDesignStatus()
  return (
    <Tabs
      value={state.tab}
      onValueChange={(tab) => dispatch({ type: 'tab', tab: tab as 'drawing' | 'renders' })}
    >
      <TabsList>
        <TabsTrigger value="drawing">
          <FileText /> {t('outputs.drawing')}
          {stale && (
            <span className="inline-flex items-center gap-1 text-xs font-normal text-amber-700">
              <span aria-hidden className="size-2 rounded-full bg-amber-500" />
              {t('outputs.stale.tab')}
            </span>
          )}
        </TabsTrigger>
        <TabsTrigger value="renders">
          <ImageIcon /> {t('outputs.renders')}
        </TabsTrigger>
      </TabsList>
      <TabsContent value="drawing">
        <DrawingTab />
      </TabsContent>
      <TabsContent value="renders" className="space-y-3">
        <StaleNotice compact />
        {state.renderJobs.map((id) => (
          <RenderProgress key={id} jobId={id} />
        ))}
        {state.renderJobs.length === 0 && (
          <p className="text-sm text-muted-foreground">{t('outputs.noRender')}</p>
        )}
        <Gallery />
      </TabsContent>
    </Tabs>
  )
}
