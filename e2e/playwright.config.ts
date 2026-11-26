import { existsSync } from 'node:fs'
import { join } from 'node:path'

import { defineConfig, devices } from '@playwright/test'

/**
 * One end-to-end run of the design flow on the FakeClient (PLAN Phase 6): the real backend
 * with an in-memory SAP and a stand-in for Blender (scripts/e2e_server.py), and the Vite
 * dev server proxying /api to it.
 */
// E2E_API_PORT and E2E_UI_PORT move the test off ports that are taken.
const API_PORT = Number(process.env.E2E_API_PORT ?? 8010)
const UI_PORT = Number(process.env.E2E_UI_PORT ?? 5174)
const venvPython = join(
  '..',
  'backend',
  '.venv',
  process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
)
const python = process.env.E2E_PYTHON ?? (existsSync(venvPython) ? venvPython : 'python')

export default defineConfig({
  testDir: './tests',
  // The README images run only through `npm run showcase` (tests/showcase.spec.ts).
  testIgnore: process.env.npm_lifecycle_event?.startsWith('showcase') ? [] : ['**/showcase.spec.ts'],
  timeout: 120_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://localhost:${UI_PORT}`,
    trace: 'retain-on-failure',
    locale: 'en-US',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } }],
  webServer: [
    {
      command: `"${python}" ../scripts/e2e_server.py --port ${API_PORT}`,
      url: `http://127.0.0.1:${API_PORT}/api/health`,
      timeout: 120_000,
      reuseExistingServer: false,
    },
    {
      command: `npm --prefix ../frontend run dev -- --port ${UI_PORT} --strictPort`,
      url: `http://localhost:${UI_PORT}`,
      env: { BEAD_API_URL: `http://127.0.0.1:${API_PORT}` },
      timeout: 120_000,
      reuseExistingServer: false,
    },
  ],
})
