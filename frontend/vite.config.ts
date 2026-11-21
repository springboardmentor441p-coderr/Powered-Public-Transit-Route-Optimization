/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The FastAPI backend has no CORS. The browser only ever talks to Vite, and Vite forwards /api to uvicorn,
// so to the browser every request is same-origin. The same proxy is used by `npm run preview`.
const api = { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: false } }

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, strictPort: true, proxy: api },
  preview: { port: 4173, strictPort: true, proxy: api },
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
})
