import { useQuery } from '@tanstack/react-query'
import { FileText, Loader2, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { api } from '@/api/client'
import type { CatalogItem } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { Gallery } from '@/studio/OutputTabs'

type Filter = 'all' | 'GLASS_BEAD' | 'CHARM' | 'new'

const STATUS_STYLE: Record<CatalogItem['status'], string> = {
  ACTIVE: 'bg-success/15 text-success',
  IN_DESIGN: 'bg-brand-amber/20 text-foreground',
  DISCONTINUED: 'bg-muted text-muted-foreground',
}

/** SAP materials (existing SKUs and the ones reserved here) and their generated files. */
export function CatalogPage() {
  const { t } = useTranslation()
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<Filter>('all')
  const catalog = useQuery({ queryKey: ['catalog'], queryFn: api.catalog })

  const items = useMemo(() => {
    const q = query.trim().toLowerCase()
    return (catalog.data ?? []).filter((item) => {
      if (filter === 'new' && item.created_by !== 'BEADSTUDIO') return false
      if ((filter === 'GLASS_BEAD' || filter === 'CHARM') && item.type !== filter) return false
      if (!q) return true
      return [item.sku, item.name, item.collection, item.family].some((v) => v?.toLowerCase().includes(q))
    })
  }, [catalog.data, query, filter])

  return (
    <div className="space-y-6">
      <section className="space-y-3 rounded-lg border bg-card p-4" aria-labelledby="catalog-title">
        <div className="flex flex-wrap items-center gap-3">
          <h2 id="catalog-title" className="mr-auto text-lg font-semibold">
            {t('catalog.title')}
          </h2>
          <div className="relative">
            <Search className="absolute top-2.5 left-2.5 size-4 text-muted-foreground" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t('catalog.search')}
              aria-label={t('catalog.search')}
              className="w-56 pl-8"
            />
          </div>
          <div className="flex rounded-md border p-0.5 text-sm" role="group" aria-label={t('catalog.filter')}>
            {(['all', 'GLASS_BEAD', 'CHARM', 'new'] as const).map((f) => (
              <button
                key={f}
                type="button"
                aria-pressed={filter === f}
                onClick={() => setFilter(f)}
                className={cn('rounded px-2.5 py-1', filter === f ? 'bg-primary text-primary-foreground' : 'hover:bg-accent')}
              >
                {t(`catalog.filters.${f}`)}
              </button>
            ))}
          </div>
        </div>
        <p className="text-sm text-muted-foreground">{t('catalog.note')}</p>

        {catalog.isPending && <Loader2 className="size-5 animate-spin text-muted-foreground" />}
        {catalog.isError && (
          <p className="text-sm text-destructive" role="alert">
            {t('catalog.sapDown')}
          </p>
        )}
        {catalog.data && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-muted-foreground">
                <tr className="border-b">
                  <th className="py-2 pr-3 font-medium">SKU</th>
                  <th className="py-2 pr-3 font-medium">{t('catalog.name')}</th>
                  <th className="py-2 pr-3 font-medium">{t('catalog.family')}</th>
                  <th className="py-2 pr-3 font-medium">{t('catalog.collection')}</th>
                  <th className="py-2 pr-3 font-medium">{t('catalog.size')}</th>
                  <th className="py-2 pr-3 font-medium">{t('catalog.status')}</th>
                  <th className="py-2 font-medium">{t('catalog.files')}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.sku} className="border-b last:border-0">
                    <td className="py-2 pr-3 font-mono">{item.sku}</td>
                    <td className="py-2 pr-3">
                      {item.name}
                      {item.created_by === 'BEADSTUDIO' && (
                        <Badge variant="outline" className="ml-2">
                          {t('catalog.new')}
                        </Badge>
                      )}
                    </td>
                    <td className="py-2 pr-3 font-mono text-xs">{item.family}</td>
                    <td className="py-2 pr-3">{item.collection}</td>
                    <td className="py-2 pr-3 font-mono tabular-nums">
                      {item.main_dimension_mm ? (
                        item.main_dimension_source === 'design' ? (
                          <span title={t('catalog.sizeFromDesign')}>
                            {item.main_dimension_mm} mm
                            <span aria-hidden className="text-muted-foreground">
                              *
                            </span>
                            <span className="sr-only"> ({t('catalog.sizeFromDesign')})</span>
                          </span>
                        ) : (
                          `${item.main_dimension_mm} mm`
                        )
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="py-2 pr-3">
                      <span className={cn('rounded px-1.5 py-0.5 text-xs font-medium', STATUS_STYLE[item.status])}>
                        {t(`catalog.statuses.${item.status}`)}
                      </span>
                    </td>
                    <td className="py-2">
                      {item.generated_revisions.length === 0 ? (
                        <span className="text-muted-foreground">—</span>
                      ) : (
                        <span className="flex flex-wrap gap-1.5">
                          {item.generated_revisions.map((rev) => (
                            <a
                              key={rev}
                              href={`/api/designs/${item.sku}/${rev}/files/drawing`}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs hover:bg-accent"
                            >
                              <FileText className="size-3" /> Rev {rev}
                            </a>
                          ))}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {items.length === 0 && <p className="py-4 text-sm text-muted-foreground">{t('catalog.none')}</p>}
          </div>
        )}
      </section>
      <section className="rounded-lg border bg-card p-4">
        <Gallery />
      </section>
    </div>
  )
}
