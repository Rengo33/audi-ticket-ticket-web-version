import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

// Point the dev proxy at a backend via VITE_API_TARGET.
// Default: production server (so `npm run dev` works out of the box for UI work).
// Override for local backend:  VITE_API_TARGET=http://localhost:8000 npm run dev
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const httpTarget = env.VITE_API_TARGET || 'https://audi-tickets.duckdns.org'
  const wsTarget = httpTarget.replace(/^http/, 'ws')

  return {
    plugins: [vue()],
    server: {
      port: 3000,
      proxy: {
        '/api': {
          target: httpTarget,
          changeOrigin: true,
          secure: false
        },
        '/ws': {
          target: wsTarget,
          changeOrigin: true,
          ws: true,
          secure: false
        },
        '/checkout': {
          target: httpTarget,
          changeOrigin: true,
          secure: false
        }
      }
    }
  }
})
