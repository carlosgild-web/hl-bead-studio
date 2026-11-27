import { defineConfig } from '@playwright/test'

/**
 * The recorder drives the app that is already running (`start.cmd video`); it never starts or
 * stops it. The page is the 1920x1080 stage, which hosts the real app in an iframe. The app's
 * origin is the UI's dev server (:5173), which proxies /api to the backend.
 */
export default defineConfig({
  testDir: '.',
  testMatch: 'record.spec.ts',
  outputDir: 'out/test-results',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 20 * 60_000,
  // A model turn, a generation (CadQuery + drawing) and a render take longer than 5 s.
  expect: { timeout: 60_000 },
  reporter: [['list']],
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:5173',
    // Edge's PDF viewer shows the drawing in the Drawing tab.
    channel: process.env.VIDEO_BROWSER_CHANNEL || 'msedge',
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
    colorScheme: 'light',
    locale: 'en-US',
    // Fail with the element's name instead of waiting for the whole test timeout.
    actionTimeout: 90_000,
  },
})
