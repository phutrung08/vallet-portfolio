import { readFileSync } from 'node:fs'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

const { version } = JSON.parse(
  readFileSync(new URL('./package.json', import.meta.url), 'utf8'),
) as { version: string }

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  define: {
    __INTLIFY_PROD_DEVTOOLS__: false,
    'import.meta.env.PACKAGE_VERSION': JSON.stringify(version),
  },
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    // Same origin in dev as in production (where a reverse proxy serves the API under /api),
    // so the API needs no CORS. changeOrigin stays false because the API validates Origin.
    proxy: {
      '/api': {
        target: process.env.VALLET_API_PROXY ?? 'http://127.0.0.1:8000',
        changeOrigin: false,
        rewrite: (path) => path.replace(/^\/api(?=\/|$)/, ''),
      },
    },
  },
  test: {
    environment: 'jsdom',
  },
})
