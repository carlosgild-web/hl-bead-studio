import { useQuery } from '@tanstack/react-query'
import { lazy, Suspense } from 'react'
import { useTranslation } from 'react-i18next'

import { fetchHealth } from '@/api/health'

// three.js is large: load the viewer in its own chunk after the first paint.
const BeadPreview = lazy(() =>
  import('@/viewer/BeadPreview').then((module) => ({ default: module.BeadPreview })),
)

function HealthStatus() {
  const { t } = useTranslation()
  const { data, isPending, isError } = useQuery({ queryKey: ['health'], queryFn: fetchHealth })

  let text = t('health.checking')
  if (isError) text = t('health.down')
  else if (!isPending) text = t('health.ok', { version: data.version, provider: data.llm_provider })

  return (
    <p className="text-sm text-muted-foreground">
      {t('health.label')}: <span className="font-medium text-foreground">{text}</span>
    </p>
  )
}

export default function App() {
  const { t, i18n } = useTranslation()
  const nextLanguage = i18n.language === 'es' ? 'en' : 'es'

  return (
    <main className="mx-auto flex min-h-svh max-w-4xl flex-col gap-6 p-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t('app.title')}</h1>
          <p className="text-muted-foreground">{t('app.subtitle')}</p>
        </div>
        <button
          type="button"
          className="rounded-md border px-3 py-1.5 text-sm hover:bg-accent"
          onClick={() => void i18n.changeLanguage(nextLanguage)}
        >
          {t('app.switchLanguage')}
        </button>
      </header>
      <HealthStatus />
      <Suspense fallback={<div className="h-80 w-full rounded-lg border bg-muted" />}>
        <BeadPreview label={t('viewer.label')} />
      </Suspense>
    </main>
  )
}
