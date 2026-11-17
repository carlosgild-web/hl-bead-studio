export interface Health {
  status: string
  version: string
  llm_provider: string
}

/** GET /api/health (proxied to the FastAPI backend in development). */
export async function fetchHealth(): Promise<Health> {
  const response = await fetch('/api/health')
  if (!response.ok) {
    throw new Error(`health check failed: HTTP ${response.status}`)
  }
  return (await response.json()) as Health
}
