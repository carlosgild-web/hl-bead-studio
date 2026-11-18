import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, CheckCircle2, Loader2, Sparkles } from 'lucide-react'
import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'

import { api } from '@/api/client'
import type { FamilyInfo, ParameterInfo, ParamValue, Validation } from '@/api/types'
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

import { useFamilyInfo, useLanguage, usePanelPreview, useStudio } from './context'

function formatValue(value: ParamValue): string {
  return typeof value === 'number' ? String(Number(value.toFixed(3))) : String(value)
}

function Field({
  name,
  info,
  family,
  value,
  proposed,
  invalid,
  onChange,
}: {
  name: string
  info: ParameterInfo
  family: FamilyInfo
  value: ParamValue | undefined
  proposed: boolean
  invalid: boolean
  onChange: (value: ParamValue) => void
}) {
  const { t } = useTranslation()
  const id = `param-${name}`
  const isOption = name === family.option_parameter
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
              {option}
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
        maxLength={40}
        onChange={(e) => onChange(e.target.value)}
        className="font-mono"
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
    </div>
  )
}

function ValidationSummary({ validation, pending }: { validation?: Validation; pending: boolean }) {
  const { t } = useTranslation()
  const { dispatch } = useStudio()
  if (!validation) return null
  if (validation.valid) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-success/40 bg-success/10 px-3 py-2 text-sm text-success" role="status">
        <CheckCircle2 className="size-4" />
        {t('panel.valid')}
        {validation.rule_edition && (
          <span className="text-xs opacity-80">· {t('panel.edition', { edition: validation.rule_edition })}</span>
        )}
        {pending && <Loader2 className="ml-auto size-4 animate-spin" />}
      </div>
    )
  }
  return (
    <div className="space-y-2" role="alert" aria-label={t('panel.violations')}>
      {validation.violations.map((v, i) => (
        <div key={`${v.rule}-${i}`} className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm">
          <div className="flex items-start gap-2">
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" />
            <div className="min-w-0 space-y-1">
              <p>
                <Badge variant="destructive" className="mr-2 font-mono">
                  {v.rule}
                </Badge>
                {v.message}
              </p>
              {v.nearest_valid && v.nearest_valid.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5 text-xs">
                  <span className="text-muted-foreground">{t('panel.nearest')}</span>
                  {v.nearest_valid.map((s) => (
                    <button
                      key={`${s.parameter}-${String(s.value)}`}
                      type="button"
                      className="rounded border bg-background px-1.5 py-0.5 font-mono hover:bg-accent"
                      onClick={() => dispatch({ type: 'edit', name: s.parameter, value: s.value })}
                    >
                      {s.parameter} = {formatValue(s.value)}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
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

      {info.data && info.data.code === state.family && (
        <>
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
                onChange={(value) => dispatch({ type: 'edit', name, value })}
              />
            ))}
          </div>
          <ValidationSummary validation={validation} pending={preview.isFetching} />
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
