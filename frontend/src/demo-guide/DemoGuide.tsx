import { ArrowUpRight, BookOpen, Compass, X } from 'lucide-react'
import { useCallback, useState, useSyncExternalStore } from 'react'

import { Dialog } from '@/components/ui/dialog'
import { cn } from '@/lib/utils'
import { useLanguage } from '@/studio/context'

import type { Bi, GuideConfig } from './guide.config'

type Mode = 'open' | 'pill'
const listeners = new Set<() => void>()
let memory: Mode | null = null

const readMode = (key: string): Mode => {
  try {
    return localStorage.getItem(key) === 'pill' ? 'pill' : 'open'
  } catch {
    return 'open'
  }
}
const writeMode = (key: string, mode: Mode) => {
  try {
    localStorage.setItem(key, mode)
  } catch {
    // Not remembered; it still changes for this visit.
  }
  memory = mode
  listeners.forEach((fn) => fn())
}

function useGuideMode(key: string): [Mode, (m: Mode) => void] {
  const subscribe = useCallback(
    (fn: () => void) => {
      listeners.add(fn)
      const onStorage = (e: StorageEvent) => {
        if (e.key === key) {
          memory = null
          fn()
        }
      }
      window.addEventListener('storage', onStorage)
      return () => {
        listeners.delete(fn)
        window.removeEventListener('storage', onStorage)
      }
    },
    [key],
  )
  const mode = useSyncExternalStore(subscribe, () => memory ?? (memory = readMode(key)))
  return [mode, (m) => writeMode(key, m)]
}

// Neutral on purpose: never the demo's brand colors.
const FRAME = 'font-sans border-dashed border-zinc-600 bg-zinc-900 text-zinc-100'

/**
 * "How this demo works": a banner above the app, a drawer with the path and things to try,
 * and a pill when hidden (remembered in localStorage). `step` marks "You are here".
 */
export function DemoGuide({ config: c, step }: { config: GuideConfig; step: number }) {
  const language = useLanguage()
  const t = (text: Bi) => text[language]
  const [mode, setMode] = useGuideMode(c.storageKey)
  const [panelOpen, setPanelOpen] = useState(false)

  const tag = (
    <span className="font-mono text-[0.65rem] tracking-[0.12em] text-zinc-400 uppercase">{t(c.tag)}</span>
  )
  const productLink = (
    <a
      href={c.productHref}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1.5 rounded-md bg-zinc-100 px-3 py-1.5 font-semibold text-zinc-900 transition-colors hover:bg-white"
    >
      {t(c.product)} <ArrowUpRight className="size-4" />
    </a>
  )

  return (
    <>
      {mode === 'open' && (
        <div role="region" aria-label={t(c.pill)} className={cn(FRAME, 'border-b')}>
          <div className="mx-auto flex max-w-[110rem] items-start gap-3 px-4 py-2.5 sm:px-6">
            <Compass className="mt-0.5 size-5 shrink-0 text-zinc-400 max-sm:hidden" />
            <div className="min-w-0 flex-1 space-y-1.5">
              {tag}
              <p className="text-sm text-zinc-200">{t(c.banner)}</p>
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <button
                  type="button"
                  onClick={() => setPanelOpen(true)}
                  className="rounded-md border border-zinc-600 px-3 py-1.5 font-semibold text-zinc-100 transition-colors hover:bg-white/10"
                >
                  {t(c.how)}
                </button>
                {productLink}
              </div>
            </div>
            <button
              type="button"
              onClick={() => setMode('pill')}
              title={t(c.hide)}
              aria-label={t(c.hide)}
              className="grid size-8 shrink-0 place-items-center rounded-md text-zinc-400 hover:bg-white/10 hover:text-white"
            >
              <X className="size-4" />
            </button>
          </div>
        </div>
      )}

      {mode === 'pill' && (
        <button
          type="button"
          onClick={() => {
            setMode('open')
            setPanelOpen(true)
          }}
          className={cn(FRAME, 'fixed bottom-4 left-4 z-40 flex items-center gap-2 rounded-full border px-3.5 py-2 text-xs font-semibold shadow-lg hover:bg-zinc-800')}
        >
          <Compass className="size-4 text-zinc-400" /> {t(c.pill)}
        </button>
      )}

      <Dialog
        open={panelOpen}
        onClose={() => setPanelOpen(false)}
        side="right"
        closeLabel={t(c.close)}
        className="font-sans"
        title={
          <span className="flex flex-col gap-1">
            <span className="font-mono text-[0.65rem] font-normal tracking-[0.12em] text-muted-foreground uppercase">{t(c.tag)}</span>
            {t(c.how)}
          </span>
        }
        description={t(c.panel.lede)}
        footer={
          <div className="flex w-full flex-wrap items-center justify-between gap-2 text-sm">
            <a
              href={c.repoUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 text-muted-foreground hover:text-foreground hover:underline"
            >
              <BookOpen className="size-4" /> {t(c.panel.repo)}
            </a>
            {productLink}
          </div>
        }
      >
        <div className="space-y-6 text-sm leading-relaxed">
          <section>
            <h3 className="font-semibold">{t(c.panel.whatTitle)}</h3>
            <p className="mt-1 text-muted-foreground">{t(c.panel.what)}</p>
          </section>
          <section>
            <h3 className="font-semibold">{t(c.panel.pathTitle)}</h3>
            <ol className="mt-2 space-y-2">
              {c.panel.steps.map((s, i) => (
                <li
                  key={s.title.en}
                  aria-current={i === step ? 'step' : undefined}
                  className={cn('flex gap-3 rounded-md border p-3', i === step ? 'border-zinc-900 bg-zinc-50 text-zinc-900' : 'border-border')}
                >
                  <span
                    className={cn(
                      'grid size-6 shrink-0 place-items-center rounded-full text-xs font-semibold',
                      i === step ? 'bg-zinc-900 text-white' : 'bg-muted text-muted-foreground',
                    )}
                  >
                    {i + 1}
                  </span>
                  <div>
                    <p className="font-medium">
                      {t(s.title)}
                      {i === step && (
                        <span className="ml-2 rounded bg-zinc-900 px-1.5 py-0.5 font-mono text-[0.6rem] tracking-wider text-white uppercase">
                          {t(c.panel.here)}
                        </span>
                      )}
                    </p>
                    <p className={i === step ? 'text-zinc-600' : 'text-muted-foreground'}>{t(s.body)}</p>
                  </div>
                </li>
              ))}
            </ol>
          </section>
          <section>
            <h3 className="font-semibold">{t(c.panel.tryTitle)}</h3>
            <ul className="mt-2 list-disc space-y-1.5 pl-5 text-muted-foreground">
              {c.panel.tries.map((item) => (
                <li key={item.en}>{t(item)}</li>
              ))}
            </ul>
          </section>
        </div>
      </Dialog>
    </>
  )
}
