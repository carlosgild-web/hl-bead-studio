import { useQuery } from '@tanstack/react-query'
import { Download, FileText, ImageIcon, Loader2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { api, renderEventsUrl, renderImageUrl } from '@/api/client'
import type { RenderJob } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

import { useLanguage, useStudio } from './context'

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

/** One render job, followed live over server-sent events until it is done or failed. */
export function RenderProgress({ jobId }: { jobId: number }) {
  const { t } = useTranslation()
  const [job, setJob] = useState<RenderJob | null>(null)

  useEffect(() => {
    const source = new EventSource(renderEventsUrl(jobId))
    source.addEventListener('status', (event) => {
      const next = JSON.parse((event as MessageEvent<string>).data) as RenderJob
      setJob(next)
      if (next.status === 'done' || next.status === 'failed') source.close()
    })
    source.onerror = () => source.close()
    return () => source.close()
  }, [jobId])

  const status = job?.status ?? 'queued'
  return (
    <div className="space-y-2 rounded-md border p-3" aria-label={t('outputs.renderJob', { id: jobId })}>
      <div className="flex items-center gap-2 text-sm">
        {(status === 'queued' || status === 'running') && <Loader2 className="size-4 animate-spin" />}
        <span className="font-medium">
          {t('outputs.renderJob', { id: jobId })}
          {job && ` · ${job.sku} Rev ${job.rev} · ${job.finish}`}
        </span>
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
      <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3">
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
  return (
    <Tabs
      value={state.tab}
      onValueChange={(tab) => dispatch({ type: 'tab', tab: tab as 'drawing' | 'renders' })}
    >
      <TabsList>
        <TabsTrigger value="drawing">
          <FileText /> {t('outputs.drawing')}
        </TabsTrigger>
        <TabsTrigger value="renders">
          <ImageIcon /> {t('outputs.renders')}
        </TabsTrigger>
      </TabsList>
      <TabsContent value="drawing">
        <DrawingTab />
      </TabsContent>
      <TabsContent value="renders" className="space-y-3">
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
