import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, CheckCircle2, Loader2, Sparkles } from 'lucide-react'
import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'

import { api } from '@/api/client'
import type { FamilyInfo, ParameterInfo, ParamValue, Validation, Violation } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'

import { dimProps, useFamilyInfo, useFocus, useLanguage, usePanelPreview, useStudio } from './context'
import { displayValue, formatNumber } from './display'
import { RuleLink } from './RuleLink'
import { PanelActions } from './PanelActions'

function Field({
  name,
  info,
  family,
  value,
  proposed,
  invalid,
  issues = [],
  onChange,
}: {
  name: string
  info: ParameterInfo
  family: FamilyInfo
  value: ParamValue | undefined
  proposed: boolean
  invalid: boolean
  issues?: Violation[]
  onChange: (value: ParamValue) => void
}) {
  const { t } = useTranslation()
  const id = `param-${name}`
  const isOption = name === family.option_parameter
  const capitals = name === 'letter' || name === 'engraving_text'
  const range =
    info.minimum !== undefined && info.maximum !== undefined
      ? `${info.minimum}–${info.maximum}${info.unit ? ` ${info.unit}` : ''}`
      : null

  let control
  if (isOption) {
    control = (
      <Select value={value === undefined ? '' : String(value)} onValueChange={onChange}>
        <SelectTrigger id={id} className="w-full" aria-invalid={invalid}>
          <SelectValue placeholder="—" />
        </SelectTrigger>
        <SelectContent>
          {family.swatches.map((s) => (
            <SelectItem key={s.id} value={s.id}>
              <span className="size-3 rounded-full border" style={{ background: s.hex }} />
              {s.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    )
  } else if (info.enum) {
    const numeric = info.type === 'number' || info.type === 'integer'
    control = (
      <Select value={value === undefined ? '' : String(value)} onValueChange={(v) => onChange(numeric ? Number(v) : v)}>
        <SelectTrigger id={id} className="w-full" aria-invalid={invalid}>
          <SelectValue placeholder="—" />
        </SelectTrigger>
        <SelectContent>
          {info.enum.map((option) => (
            <SelectItem key={option} value={String(option)}>
              {typeof option === 'number' ? formatNumber(option) : (info.choices?.[option] ?? option)}
              {info.unit && ` ${info.unit}`}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    )
  } else if (info.type === 'boolean') {
    control = (
      <input
        id={id}
        type="checkbox"
        className="size-4 accent-primary"
        checked={value === true}
        onChange={(e) => onChange(e.target.checked)}
      />
    )
  } else if (info.type === 'number' || info.type === 'integer') {
    control = (
      <div className="flex items-center gap-2">
        <Input
          id={id}
          type="number"
          inputMode="decimal"
          step={info.step ?? (info.type === 'integer' ? 1 : 0.1)}
          min={info.minimum}
          max={info.maximum}
          aria-invalid={invalid}
          value={value === undefined ? '' : String(value)}
          onChange={(e) => {
            const text = e.target.value
            const parsed = info.type === 'integer' ? parseInt(text, 10) : parseFloat(text)
            onChange(Number.isNaN(parsed) ? text : parsed)
          }}
          className="font-mono tabular-nums"
        />
        {info.unit && <span className="w-8 text-sm text-muted-foreground">{info.unit}</span>}
      </div>
    )
  } else {
    control = (
      <Input
        id={id}
        aria-invalid={invalid}
        value={value === undefined ? '' : String(value)}
        // A letter is one capital (CH-07) and an engraving is capitals too (CH-06): typed
        // lowercase, they are shown and sent uppercase.
        maxLength={name === 'letter' ? 1 : name === 'engraving_text' ? 12 : 40}
        autoCapitalize={capitals ? 'characters' : undefined}
        onChange={(e) => onChange(capitals ? e.target.value.toUpperCase() : e.target.value)}
        className={cn('font-mono', capitals && 'uppercase')}
      />
    )
  }

  return (
    <div
      className={cn(
        'grid gap-1.5 rounded-md p-2 transition-colors',
        proposed && 'bg-proposed ring-1 ring-brand-amber/60',
      )}
      data-proposed={proposed || undefined}
    >
      <div className="flex items-center justify-between gap-2">
        <label htmlFor={id} className="text-sm font-medium">
          {info.label}
        </label>
        <span className="flex items-center gap-1.5">
          {proposed && (
            <span className="inline-flex items-center gap-1 text-xs text-brand-amber">
              <Sparkles className="size-3" /> {t('panel.proposed')}
            </span>
          )}
          {range && <span className="font-mono text-xs text-muted-foreground">{range}</span>}
        </span>
      </div>
      {control}
      {issues.map((v, i) => (
        <ViolationNote key={`${v.rule}-${i}`} v={v} family={family} />
      ))}
    </div>
  )
}

/** One broken rule: its id, the message in the UI language and the nearest valid values. */
function ViolationNote({ v, family }: { v: Violation; family?: FamilyInfo }) {
  const { t } = useTranslation()
  const { dispatch } = useStudio()
  const language = useLanguage()
  return (
    <div className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm">
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" />
        <div className="min-w-0 space-y-1">
          <p>
            <Badge variant="destructive" className="mr-2 font-mono">
              <RuleLink rule={v.rule} />
            </Badge>
            {language === 'es' && v.message_es ? v.message_es : v.message}
          </p>
          {v.nearest_valid && v.nearest_valid.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 text-xs">
              <span className="text-muted-foreground">{t('panel.nearest')}</span>
              {v.nearest_valid.map((s) => (
                <button
                  key={`${s.parameter}-${String(s.value)}`}
                  type="button"
                  className="rounded border bg-background px-1.5 py-0.5 hover:bg-accent"
                  onClick={() => dispatch({ type: 'edit', name: s.parameter, value: s.value })}
                >
                  {family?.parameters[s.parameter]?.label ?? t('panel.value')}{' '}
                  {displayValue(family?.parameters[s.parameter], s.value, t)}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

/** A violation about one field is shown under that field (QA 2026-11-23, item 10). */
function fieldOf(v: Violation, family?: FamilyInfo): string | null {
  return v.parameters.length === 1 && family?.parameters[v.parameters[0]] ? v.parameters[0] : null
}

function ValidationSummary({
  validation,
  pending,
  family,
}: {
  validation?: Validation
  pending: boolean
  family?: FamilyInfo
}) {
  const { t } = useTranslation()
  const language = useLanguage()
  if (!validation) return null
  if (validation.valid) {
    // The edition text comes from the manual in English ("Edition 1 (2026-11)").
    const edition =
      language === 'es' ? validation.rule_edition.replace(/^Edition /, 'Edición ') : validation.rule_edition
    return (
      <div className="flex items-center gap-2 rounded-md border border-success/40 bg-success/10 px-3 py-2 text-sm text-success" role="status">
        <CheckCircle2 className="size-4" />
        {t('panel.valid')}
        {validation.rule_edition && (
          <span className="text-xs opacity-80">· {t('panel.edition', { edition })}</span>
        )}
        {pending && <Loader2 className="ml-auto size-4 animate-spin" />}
      </div>
    )
  }
  const general = validation.violations.filter((v) => fieldOf(v, family) === null)
  const atFields = validation.violations.filter((v) => fieldOf(v, family) !== null)
  return (
    <div className="space-y-2" role="alert" aria-label={t('panel.violations')}>
      {atFields.length > 0 && (
        <p className="flex flex-wrap items-center gap-1.5 text-sm text-destructive">
          <AlertTriangle className="size-4 shrink-0" />
          {t('panel.seeFields', {
            fields: [...new Set(atFields.map((v) => family?.parameters[v.parameters[0]]?.label ?? ''))].join(', '),
          })}
          {[...new Set(atFields.map((v) => v.rule))].map((rule) => (
            <Badge key={rule} variant="destructive" className="font-mono">
              <RuleLink rule={rule} />
            </Badge>
          ))}
        </p>
      )}
      {general.map((v, i) => (
        <ViolationNote key={`${v.rule}-${i}`} v={v} family={family} />
      ))}
    </div>
  )
}

export function ParameterPanel() {
  const { t } = useTranslation()
  const language = useLanguage()
  const { state, dispatch } = useStudio()
  const families = useQuery({
    queryKey: ['families', language],
    queryFn: () => api.families(language),
    staleTime: Infinity,
  })
  const info = useFamilyInfo(state.family)
  const stepFocus = useFocus()?.kind === 'step'
  const preview = usePanelPreview(state.family, state.params)
  const validation =
    preview.data?.validation.family === state.family ? preview.data?.validation : undefined

  useEffect(() => {
    if (info.data && info.data.code === state.family) {
      dispatch({ type: 'fillDefaults', family: info.data.code, params: info.data.defaults })
    }
  }, [info.data, state.family, dispatch])

  const invalid = new Set(validation?.violations.flatMap((v) => v.parameters) ?? [])
  const beads = families.data?.filter((f) => f.kind === 'glass_bead') ?? []
  const charms = families.data?.filter((f) => f.kind === 'charm') ?? []

  return (
    <section aria-labelledby="panel-title" className="flex min-h-0 flex-col gap-3">
      {/* While a workflow step waits for its form, only the workflow stays sharp. */}
      <div {...dimProps(stepFocus, 'flex flex-col gap-3')}>
      <div className="flex items-center justify-between gap-2">
        <h2 id="panel-title" className="font-semibold">
          {t('panel.title')}
        </h2>
        {state.reserved && (
          <Badge variant="secondary" className="font-mono">
            {state.reserved.sku}
          </Badge>
        )}
      </div>

      <div className="grid gap-1.5">
        <label htmlFor="family" className="text-sm font-medium">
          {t('panel.family')}
        </label>
        <Select
          value={state.family ?? ''}
          onValueChange={(code) => dispatch({ type: 'chooseFamily', family: code })}
        >
          <SelectTrigger id="family" className="w-full">
            <SelectValue placeholder={t('panel.chooseFamily')} />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectLabel>{t('panel.beads')}</SelectLabel>
              {beads.map((f) => (
                <SelectItem key={f.code} value={f.code}>
                  {f.name} <span className="font-mono text-xs text-muted-foreground">{f.code}</span>
                </SelectItem>
              ))}
            </SelectGroup>
            <SelectGroup>
              <SelectLabel>{t('panel.charms')}</SelectLabel>
              {charms.map((f) => (
                <SelectItem key={f.code} value={f.code}>
                  {f.name} <span className="font-mono text-xs text-muted-foreground">{f.code}</span>
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      </div>

      {!state.family && (
        <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
          {t('panel.empty')}
        </p>
      )}

      </div>

      {info.data && info.data.code === state.family && (
        <>
          <div {...dimProps(stepFocus, 'flex flex-col gap-3')}>
          <p className="text-xs text-muted-foreground">
            {t('panel.material', {
              material: info.data.material,
              density: info.data.density_g_cm3,
            })}
          </p>
          <div className="grid gap-1 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
            {Object.entries(info.data.parameters).map(([name, p]) => (
              <Field
                key={name}
                name={name}
                info={p}
                family={info.data}
                value={state.params[name]}
                proposed={state.proposed.includes(name)}
                invalid={invalid.has(name)}
                issues={validation?.violations.filter((v) => fieldOf(v, info.data) === name)}
                onChange={(value) => dispatch({ type: 'edit', name, value })}
              />
            ))}
          </div>
          <ValidationSummary validation={validation} pending={preview.isFetching} family={info.data} />
          </div>
          <PanelActions family={info.data} validation={validation} />
          {preview.isError && (
            <p className="text-sm text-destructive" role="alert">
              {t('panel.checkFailed')}
            </p>
          )}
        </>
      )}
    </section>
  )
}
