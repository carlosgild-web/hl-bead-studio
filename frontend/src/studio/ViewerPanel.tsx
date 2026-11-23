import { Box, Loader2 } from 'lucide-react'
import { lazy, Suspense } from 'react'
import { useTranslation } from 'react-i18next'

import { cn } from '@/lib/utils'

import { useFamilyInfo, usePanelPreview, useStudio } from './context'

// three.js is large: the viewer loads in its own chunk after the first paint.
const BeadPreview = lazy(() =>
  import('@/viewer/BeadPreview').then((module) => ({ default: module.BeadPreview })),
)

export function ViewerPanel() {
  const { t } = useTranslation()
  const { state, dispatch } = useStudio()
  const info = useFamilyInfo(state.family)
  const preview = usePanelPreview(state.family, state.params)
  const current = preview.data?.validation.family === state.family ? preview.data : undefined
  const family = info.data?.code === state.family ? info.data : undefined
  const option = family?.option_parameter
  const selected = option ? String(state.params[option] ?? '') : ''
  const swatch = family?.swatches.find((s) => s.id === selected)
  const m = current?.preview?.measurements

  return (
    <section aria-labelledby="viewer-title" className="flex min-h-0 flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 id="viewer-title" className="font-semibold">
          {t('viewer.title')}
        </h2>
        {preview.isFetching && <Loader2 className="size-4 animate-spin text-muted-foreground" aria-label={t('viewer.building')} />}
      </div>
      <div className="relative aspect-square w-full overflow-hidden rounded-lg border bg-[#f3f0ea]">
        {current?.preview && family ? (
          <Suspense fallback={<div className="size-full animate-pulse bg-muted" />}>
            <BeadPreview
              url={current.preview.url}
              kind={family.kind}
              swatch={swatch}
              label={t('viewer.label', { family: family.name })}
            />
          </Suspense>
        ) : (
          <div className="grid size-full place-items-center p-6 text-center text-sm text-muted-foreground">
            <div className="space-y-2">
              <Box className="mx-auto size-8 opacity-50" />
              <p>{current && !current.validation.valid ? t('viewer.invalid') : t('viewer.empty')}</p>
            </div>
          </div>
        )}
      </div>

      {family && option && (
        <div>
          <p className="mb-1.5 text-xs font-medium text-muted-foreground">
            {option === 'color' ? t('viewer.color') : t('viewer.finish')}: {swatch?.name ?? '—'}
          </p>
          <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label={option === 'color' ? t('viewer.color') : t('viewer.finish')}>
            {family.swatches.map((s) => (
              <button
                key={s.id}
                type="button"
                role="radio"
                aria-checked={s.id === selected}
                title={s.name}
                aria-label={s.name}
                onClick={() => dispatch({ type: 'edit', name: option, value: s.id })}
                className={cn(
                  'size-6 rounded-full border-2 border-white shadow-sm ring-1 ring-border transition-transform hover:scale-110',
                  s.id === selected && 'ring-2 ring-primary',
                )}
                style={{ background: s.hex }}
              />
            ))}
          </div>
        </div>
      )}

      {m && (
        <dl className="grid grid-cols-3 gap-2 text-sm" aria-label={t('viewer.measurements')}>
          <div className="rounded-md bg-muted px-2 py-1.5">
            <dt className="text-xs text-muted-foreground">{t('viewer.size')}</dt>
            <dd className="font-mono tabular-nums">{m.bbox_mm.map((v) => v.toFixed(1)).join(' × ')} mm</dd>
          </div>
          <div className="rounded-md bg-muted px-2 py-1.5">
            <dt className="text-xs text-muted-foreground">{t('viewer.volume')}</dt>
            <dd className="font-mono tabular-nums">{m.volume_mm3.toFixed(1)} mm³</dd>
          </div>
          <div className="rounded-md bg-muted px-2 py-1.5">
            <dt className="text-xs text-muted-foreground">{t('viewer.mass')}</dt>
            <dd className="font-mono tabular-nums">{m.mass_g.toFixed(3)} g</dd>
          </div>
        </dl>
      )}
      {m && info.data?.kind === 'charm' && (
        // The height field is the body; the loop adds to what the charm measures (QA item 15).
        <p className="text-xs text-muted-foreground">{t('viewer.overallHeight', { height: m.bbox_mm[1].toFixed(1) })}</p>
      )}
    </section>
  )
}
