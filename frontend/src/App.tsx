import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { api } from '@/api/client'
import { CatalogPage } from '@/catalog/CatalogPage'
import { DemoGuide } from '@/demo-guide/DemoGuide'
import { guide } from '@/demo-guide/guide.config'
import { cn } from '@/lib/utils'
import { useStudio } from '@/studio/context'
import { currentStep } from '@/studio/state'
import { StudioProvider } from '@/studio/StudioProvider'
import { StudioPage } from '@/studio/StudioPage'

type View = 'studio' | 'catalog'

function HealthStatus() {
  const { t } = useTranslation()
  const { data, isPending, isError } = useQuery({ queryKey: ['health'], queryFn: api.health })

  let text = t('health.checking')
  if (isError) text = t('health.down')
  else if (!isPending) text = t('health.ok', { version: data.version, provider: data.llm_provider })

  return (
    <p className="text-xs text-muted-foreground">
      {t('health.label')}: <span className={cn('font-medium', isError ? 'text-destructive' : 'text-foreground')}>{text}</span>
    </p>
  )
}

function Shell() {
  const { t, i18n } = useTranslation()
  const { state } = useStudio()
  const [view, setView] = useState<View>('studio')
  const nextLanguage = i18n.language === 'es' ? 'en' : 'es'

  return (
    <div className="min-h-svh">
      <DemoGuide config={guide} step={currentStep(state)} />
      <header className="border-b bg-brand-navy text-white">
        <div className="mx-auto flex max-w-[110rem] flex-wrap items-center gap-x-6 gap-y-2 px-4 py-2.5 sm:px-6">
          <div className="flex items-center gap-3">
            <img src="/hl_logo.svg" alt="" className="h-9 rounded bg-white p-0.5" />
            <div>
              <h1 className="text-lg leading-tight font-semibold tracking-tight">{t('app.title')}</h1>
              <p className="text-xs text-white/70">{t('app.subtitle')}</p>
            </div>
          </div>
          <nav aria-label={t('app.nav')} className="flex gap-1">
            {(['studio', 'catalog'] as const).map((v) => (
              <button
                key={v}
                type="button"
                aria-current={view === v ? 'page' : undefined}
                onClick={() => setView(v)}
                className={cn(
                  'rounded-md px-3 py-1.5 text-sm font-medium',
                  view === v ? 'bg-white text-brand-navy' : 'text-white/80 hover:bg-white/10',
                )}
              >
                {t(`app.views.${v}`)}
              </button>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-4 [&_p]:text-white/70 [&_span]:text-white">
            <HealthStatus />
            <button
              type="button"
              className="rounded-md border border-white/30 px-3 py-1.5 text-sm hover:bg-white/10"
              onClick={() => void i18n.changeLanguage(nextLanguage)}
            >
              {t('app.switchLanguage')}
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[110rem] p-4 sm:px-6">
        {view === 'studio' ? <StudioPage /> : <CatalogPage />}
      </main>
    </div>
  )
}

export default function App() {
  return (
    <StudioProvider>
      <Shell />
    </StudioProvider>
  )
}
