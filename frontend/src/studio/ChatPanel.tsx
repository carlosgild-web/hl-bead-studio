import type { TFunction } from 'i18next'
import { AlertCircle, ArrowRight, Bot, ChevronRight, Loader2, Send, Wrench } from 'lucide-react'
import { type FormEvent, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import type { FamilyInfo } from '@/api/types'

import { ActionCard } from './ActionCard'
import { type CardRequest, useFamilyInfo, useOpenCard, useStudio } from './context'
import type { StudioState, ToolStep } from './state'

const EXAMPLES = ['chat.example1', 'chat.example2', 'chat.example3'] as const

function Steps({ steps }: { steps: ToolStep[] }) {
  const { t } = useTranslation()
  return (
    <details className="group rounded-md border border-dashed px-2 py-1 text-xs text-muted-foreground">
      <summary className="flex cursor-pointer list-none items-center gap-1.5">
        <ChevronRight className="size-3 transition-transform group-open:rotate-90" />
        <Wrench className="size-3" />
        {t('chat.steps', { count: steps.length })}
      </summary>
      <ol className="mt-1 space-y-1 pl-5">
        {steps.map((s) => (
          <li key={s.id}>
            <span className={cn('font-mono', s.ok === false && 'text-destructive')}>{s.name}</span>
            {s.ok === undefined && <Loader2 className="ml-1 inline size-3 animate-spin" />}
            {s.ok === false && ` · ${t('chat.stepFailed')}`}
          </li>
        ))}
      </ol>
    </details>
  )
}

/** Assistant text: plain text with line breaks and **bold** (no HTML is ever injected). */
function AssistantText({ text }: { text: string }) {
  return (
    <div className="space-y-2 whitespace-pre-wrap">
      {text.split(/\n{2,}/).map((paragraph, i) => (
        <p key={i}>
          {paragraph.split(/(\*\*[^*]+\*\*)/g).map((part, j) =>
            part.startsWith('**') && part.endsWith('**') ? (
              <strong key={j}>{part.slice(2, -2)}</strong>
            ) : (
              part
            ),
          )}
        </p>
      ))}
    </div>
  )
}

/**
 * After a confirmed card, the next card of the flow. The chip opens it directly, the same
 * way as the panel's workflow (not through the assistant, so it works with any provider);
 * the designer still confirms it (invariant 2).
 */
function nextStep(
  state: StudioState,
  family: FamilyInfo | undefined,
  t: TFunction,
): { label: string; request: CardRequest } | null {
  const open = (kind: string) =>
    Object.values(state.actions).some((a) => a.kind === kind && a.status === 'pending')
  if (state.design && state.renderJobs.length === 0 && !open('render')) {
    const finish = family ? state.params[family.option_parameter] : undefined
    return {
      label: t('chat.next.render', { sku: state.design.sku, rev: state.design.rev }),
      request: { kind: 'render', sku: state.design.sku, rev: state.design.rev, finish: String(finish ?? '') },
    }
  }
  if (state.reserved && !state.design && !open('generate_design')) {
    return {
      label: t('chat.next.generate', { sku: state.reserved.sku }),
      request: {
        kind: 'generate_design',
        family: state.family ?? '',
        sku: state.reserved.sku,
        rev: 'A',
        params: state.params,
      },
    }
  }
  return null
}

export function ChatPanel() {
  const { t } = useTranslation()
  const { state, send } = useStudio()
  const family = useFamilyInfo(state.family)
  const card = useOpenCard()
  const [text, setText] = useState('')
  const list = useRef<HTMLDivElement>(null)
  const next = state.busy ? null : nextStep(state, family.data, t)

  // Scroll the chat list only (scrollIntoView also scrolled the page), smoothly to its end,
  // so a new card is just in view.
  useEffect(() => {
    const box = list.current
    box?.scrollTo?.({ top: box.scrollHeight, behavior: 'smooth' })
  }, [state.items.length, state.busy])

  function submit(event?: FormEvent) {
    event?.preventDefault()
    const message = text.trim()
    if (!message || state.busy) return
    setText('')
    void send(message)
  }

  return (
    <section aria-labelledby="chat-title" className="flex min-h-[28rem] flex-col rounded-lg border bg-card lg:h-full lg:min-h-0">
      <header className="flex items-center gap-2 border-b px-4 py-3">
        <Bot className="size-4 text-primary" />
        <h2 id="chat-title" className="font-semibold">
          {t('chat.title')}
        </h2>
      </header>

      <div ref={list} className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4" aria-live="polite">
        {state.items.length === 0 && (
          <div className="space-y-3 text-sm text-muted-foreground">
            <p>{t('chat.intro')}</p>
            <div className="flex flex-col gap-1.5">
              {EXAMPLES.map((key) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setText(t(key))}
                  className="rounded-md border bg-background px-3 py-2 text-left text-foreground hover:bg-accent"
                >
                  {t(key)}
                </button>
              ))}
            </div>
          </div>
        )}
        {state.items.map((item, i) => {
          switch (item.kind) {
            case 'user':
              return (
                <div key={i} className="ml-8 rounded-lg bg-primary px-3 py-2 text-sm whitespace-pre-wrap text-primary-foreground">
                  {item.text}
                </div>
              )
            case 'assistant':
              return (
                <div key={i} className="mr-4 rounded-lg bg-muted px-3 py-2 text-sm" data-role="assistant">
                  <AssistantText text={item.text} />
                </div>
              )
            case 'steps':
              return <Steps key={i} steps={item.steps} />
            case 'action': {
              const action = state.actions[item.actionId]
              return action ? <ActionCard key={i} action={action} /> : null
            }
            case 'error':
              return (
                <p key={i} role="alert" className="flex items-start gap-2 rounded-md border border-destructive/40 px-3 py-2 text-sm text-destructive">
                  <AlertCircle className="mt-0.5 size-4 shrink-0" /> {item.text}
                </p>
              )
          }
        })}
        {state.busy && (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" /> {t('chat.thinking')}
          </p>
        )}
      </div>

      {next && (
        <div className="flex flex-wrap items-center gap-2 border-t px-3 pt-3 text-sm">
          <span className="text-muted-foreground">{t('chat.next.label')}</span>
          <button
            type="button"
            disabled={card.working}
            onClick={() => void card.open(next.request)}
            className="inline-flex items-center gap-1.5 rounded-full border border-primary/40 bg-primary/5 px-3 py-1 font-medium text-primary hover:bg-primary/10 disabled:opacity-60"
          >
            {card.working && <Loader2 className="size-3.5 animate-spin" />}
            {next.label} <ArrowRight className="size-3.5" />
          </button>
          {card.error && (
            <p role="alert" className="w-full text-xs whitespace-pre-line text-destructive">
              {t('chat.next.failed')} {card.error}
            </p>
          )}
        </div>
      )}
      <form onSubmit={submit} className={cn('flex items-end gap-2 p-3', !next && 'border-t')}>
        <label htmlFor="chat-input" className="sr-only">
          {t('chat.placeholder')}
        </label>
        <textarea
          id="chat-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) submit(e)
          }}
          maxLength={2000}
          rows={2}
          placeholder={t('chat.placeholder')}
          className="min-h-10 flex-1 resize-none rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
        />
        <Button type="submit" size="icon" disabled={state.busy || !text.trim()} aria-label={t('chat.send')}>
          <Send />
        </Button>
      </form>
    </section>
  )
}
