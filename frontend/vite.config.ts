import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/auth': 'http://127.0.0.1:8000',
      '/dashboard': 'http://127.0.0.1:8000',
      '/crowd': 'http://127.0.0.1:8000',
      '/schedule': 'http://127.0.0.1:8000',
      '/scheduling': 'http://127.0.0.1:8000',
      '/monitor': 'http://127.0.0.1:8000',
      '/predict': 'http://127.0.0.1:8000',
      '/analytics': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
      '/alerts': 'http://127.0.0.1:8000',
      '/notifications': 'http://127.0.0.1:8000',
      '/announcements': 'http://127.0.0.1:8000',
      '/schedule-updates': 'http://127.0.0.1:8000',
      '/docs': 'http://127.0.0.1:8000',
      '/openapi.json': 'http://127.0.0.1:8000',
    }
  }
})
