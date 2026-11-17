import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import i18n from '@/i18n'

import App from './App'

// jsdom has no WebGL: the three.js canvas is replaced by a stub in unit tests.
vi.mock('@/viewer/BeadPreview', () => ({
  BeadPreview: ({ label }: { label: string }) => <div aria-label={label} />,
}))

function renderApp() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  )
}

describe('App', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('en')
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows the title and the backend status from /api/health', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ status: 'ok', version: '0.1.0', llm_provider: 'fake' })),
      ),
    )

    renderApp()

    expect(screen.getByRole('heading', { name: 'Bead Studio' })).toBeInTheDocument()
    expect(await screen.findByText('ok (v0.1.0, LLM: fake)')).toBeInTheDocument()
    expect(await screen.findByLabelText('3D preview (placeholder bead)')).toBeInTheDocument()
  })

  it('says when the backend is not reachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 502 })))

    renderApp()

    expect(await screen.findByText('not reachable')).toBeInTheDocument()
  })

  it('switches the interface to Spanish', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 502 })))

    renderApp()
    fireEvent.click(screen.getByRole('button', { name: 'Español' }))

    expect(await screen.findByText('Hilda & Luna Beadworks · Diseño de Producto')).toBeInTheDocument()
    expect(await screen.findByText('no disponible')).toBeInTheDocument()
  })
})
