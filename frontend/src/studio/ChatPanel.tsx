import { useQuery } from '@tanstack/react-query'
import type { TFunction } from 'i18next'
import { AlertCircle, ArrowDown, ArrowRight, Bot, ChevronRight, Loader2, RotateCcw, Send, Wrench } from 'lucide-react'
import { type FormEvent, type ReactNode, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { api } from '@/api/client'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'


import { ActionCard } from './ActionCard'
import { WithRuleLinks } from './RuleLink'
import { dimProps, goToCard, useFocus, useOpenCard, useRenderJob, useStudio } from './context'
import type { ChatItem, StepId, StudioState, ToolStep } from './state'

const EXAMPLES = ['chat.example1', 'chat.example2', 'chat.example3'] as const
// Questions from the Q&A bank, shown in demo mode (decision 0022).
const QUESTIONS = ['chat.question1', 'chat.question2'] as const

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
              <strong key={j}>
                <WithRuleLinks text={part.slice(2, -2)} />
              </strong>
            ) : (
              <WithRuleLinks key={j} text={part} />
            ),
          )}
        </p>
      ))}
    </div>
  )
}

type NextStep = { label: string; step: StepId } | { label: string; reset: true }

/**
 * After a confirmed card, the next step of the flow. The chip points to it in the panel's
 * workflow, opens its form there and waits (focus mode); the form opens the card and the
 * designer confirms it (invariant 2). Once the render is finished, it offers a new design.
 */
function nextStep(state: StudioState, renderFinished: boolean, t: TFunction): NextStep | null {
  const open = (kind: string) =>
    Object.values(state.actions).some((a) => a.kind === kind && a.status === 'pending')
  if (state.design && renderFinished && !open('render')) {
    return { label: t('chat.next.newDesign'), reset: true }
  }
  if (state.design && state.renderJobs.length === 0 && !open('render')) {
    return { label: t('chat.next.render', { sku: state.design.sku, rev: state.design.rev }), step: 'render' }
  }
  if (state.reserved && !state.design && !open('generate_design')) {
    return { label: t('chat.next.generate', { sku: state.reserved.sku }), step: 'generate' }
  }
  return null
}

export function ChatPanel() {
  const { t } = useTranslation()
  const { state, dispatch, send } = useStudio()
  const card = useOpenCard()
  const [text, setText] = useState('')
  const list = useRef<HTMLDivElement>(null)
  const health = useQuery({ queryKey: ['health'], queryFn: api.health })
  const demo = health.data?.llm_provider === 'fake'
  const chips = demo ? [...EXAMPLES, ...QUESTIONS] : EXAMPLES
  const lastJob = useRenderJob(state.renderJobs[0] ?? null)
  const renderFinished = lastJob?.status === 'done' || lastJob?.status === 'failed'
  const next = state.busy ? null : nextStep(state, renderFinished, t)
  const confirmingReset = state.asking === 'reset'
  const setConfirmingReset = (ask: boolean) => dispatch({ type: 'ask', question: ask ? 'reset' : null })
  const started = state.items.length > 0 || state.family !== null
  // Focus mode: while a decision waits, everything but it is dimmed and inert.
  const focus = useFocus()
  const focusing = focus !== null
  const focusedCard = focus?.kind === 'card' ? focus.actionId : null
  const keepWorking = useRef<HTMLButtonElement>(null)

  function startOver() {
    card.clearError()
    setText('')
    dispatch({ type: 'reset' })
  }

  // Scroll the chat list only (scrollIntoView also scrolled the page), smoothly to its end,
  // so a new card is just in view.
  useEffect(() => {
    const box = list.current
    box?.scrollTo?.({ top: box.scrollHeight, behavior: 'smooth' })
  }, [state.items.length, state.busy])

  // The decision in focus is brought into view and gets the keyboard focus.
  useEffect(() => {
    if (focusedCard) goToCard(focusedCard)
    else if (focus?.kind === 'reset') keepWorking.current?.focus()
  }, [focusedCard, focus?.kind])

  function submit(event?: FormEvent) {
    event?.preventDefault()
    const message = text.trim()
    if (!message || state.busy) return
    setText('')
    void send(message)
  }

  /** One chat item as the chat shows it. */
  function chatItem(item: ChatItem): ReactNode {
    switch (item.kind) {
      case 'user':
        return (
          <div className="ml-8 rounded-lg bg-primary px-3 py-2 text-sm whitespace-pre-wrap text-primary-foreground">{item.text}</div>
        )
      case 'assistant':
        return (
          <div className="mr-4 rounded-lg bg-muted px-3 py-2 text-sm" data-role="assistant">
            <AssistantText text={item.text} />
          </div>
        )
      case 'steps':
        return <Steps steps={item.steps} />
      case 'action': {
        const action = state.actions[item.actionId]
        return action ? <ActionCard action={action} focused={action.id === focusedCard} /> : null
      }
      case 'error':
        return (
          <p role="alert" className="flex items-start gap-2 rounded-md border border-destructive/40 px-3 py-2 text-sm text-destructive">
            <AlertCircle className="mt-0.5 size-4 shrink-0" /> {item.text}
          </p>
        )
    }
  }

  return (
    <section aria-labelledby="chat-title" className="flex min-h-[28rem] flex-col rounded-lg border bg-card lg:h-full lg:min-h-0">
      <header {...dimProps(focusing, 'flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 border-b px-4 py-3')}>
        <Bot className="size-4 text-primary" />
        <h2 id="chat-title" className="min-w-0 font-semibold">
          {t('chat.title')}
        </h2>
        {demo && (
          <Badge
            variant="outline"
            className="ml-auto cursor-help border-brand-amber/60 bg-brand-amber/10"
            title={[t('chat.demo.tooltip'), health.data?.llm_note].filter(Boolean).join(' ')}
          >
            {t('chat.demo.badge')}
          </Badge>
        )}
        {started && (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className={cn('h-7 px-2 text-xs', !demo && 'ml-auto')}
            disabled={state.busy}
            aria-expanded={confirmingReset}
            onClick={() => setConfirmingReset(!confirmingReset)}
          >
            <RotateCcw className="size-3.5" /> <span className="max-sm:sr-only">{t('chat.newDesign')}</span>
          </Button>
        )}
      </header>
      {confirmingReset && (
        <div
          role="alertdialog"
          aria-label={t('chat.newDesign')}
          className="space-y-2 border-b bg-muted/40 px-4 py-3 text-sm ring-2 ring-primary/40 ring-inset"
          onKeyDown={(e) => {
            if (e.key === 'Escape') setConfirmingReset(false)
          }}
        >
          <p>{t('chat.newDesignConfirm')}</p>
          <div className="flex gap-2">
            <Button type="button" size="sm" onClick={startOver}>
              {t('chat.newDesignYes')}
            </Button>
            <Button ref={keepWorking} type="button" size="sm" variant="outline" onClick={() => setConfirmingReset(false)}>
              {t('chat.newDesignNo')}
            </Button>
          </div>
        </div>
      )}

      <div ref={list} className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4" aria-live="polite">
        {state.items.length === 0 && (
          <div {...dimProps(focusing, 'space-y-3 text-sm text-muted-foreground')}>
            <p>{t('chat.intro')}</p>
            <div className="flex flex-col gap-1.5">
              {chips.map((key) => (
                <button
                  key={key}
                  type="button"
                  disabled={state.busy}
                  onClick={() => void send(t(key))}
                  className="rounded-md border bg-background px-3 py-2 text-left text-foreground hover:bg-accent"
                >
                  {t(key)}
                </button>
              ))}
            </div>
          </div>
        )}
        {state.items.map((item, i) => (
          // The same wrapper either way, so dimming never remounts an item.
          <div key={i} {...dimProps(focusing && !(item.kind === 'action' && item.actionId === focusedCard))}>
            {chatItem(item)}
          </div>
        ))}
        {state.busy && (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" /> {t('chat.thinking')}
          </p>
        )}
      </div>

      {state.proposed.length > 0 && !state.busy && (
        // On a phone the panel is far below the chat: a cue that the values arrived there.
        <button
          type="button"
          className="mx-3 mb-1 inline-flex items-center gap-1 self-start text-sm font-medium text-primary underline-offset-2 hover:underline lg:hidden"
          onClick={() =>
            document.getElementById('panel-title')?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
          }
        >
          {t('chat.seeParameters')} <ArrowDown className="size-3.5" />
        </button>
      )}
      {next && (
        <div {...dimProps(focusing, 'flex flex-wrap items-center gap-2 border-t px-3 pt-3 text-sm')}>
          <span className="text-muted-foreground">{t('chat.next.label')}</span>
          <button
            type="button"
            disabled={card.working || ('step' in next && state.openStep === next.step)}
            onClick={() => ('reset' in next ? setConfirmingReset(true) : dispatch({ type: 'openStep', step: next.step }))}
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
      <form onSubmit={submit} {...dimProps(focusing, cn('flex items-end gap-2 p-3', !next && 'border-t'))}>
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
