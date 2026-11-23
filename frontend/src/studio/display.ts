import type { TFunction } from 'i18next'

import type { ParameterInfo, ParamValue } from '@/api/types'

/** A number as the panel shows it: up to 3 decimals, no trailing zeros. */
export function formatNumber(value: number): string {
  return String(Number(value.toFixed(3)))
}

/**
 * A parameter value as the designer reads it: "20 mm", "Gold plate", "Yes". Never the raw
 * key of a choice (gold_plate) or a bare boolean.
 */
export function displayValue(info: ParameterInfo | undefined, value: ParamValue, t: TFunction): string {
  if (typeof value === 'boolean') return value ? t('common.yes') : t('common.no')
  if (typeof value === 'number') return `${formatNumber(value)}${info?.unit ? ` ${info.unit}` : ''}`
  return info?.choices?.[value] ?? value
}
