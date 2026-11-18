/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    // three.js and drei (~1.07 MB minified) live in the lazily loaded viewer chunk, not in
    // the first load; warn only if a chunk grows past that.
    chunkSizeWarningLimit: 1100,
  },
  server: {
    // The FastAPI backend (uvicorn app.main:app --port 8000); the e2e test points
    // BEAD_API_URL at its own backend.
    proxy: {
      '/api': process.env.BEAD_API_URL ?? 'http://localhost:8000',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
