import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Хосты, с которых разрешено обслуживать dev-сервер (Vite блокирует чужой Host).
// За reverse-proxy (Caddy) на проде Host = публичный домен, поэтому добавляем
// .sslip.io и значение из VITE_ALLOWED_HOSTS. Локально работает localhost.
const allowedHosts = [
  'localhost',
  '127.0.0.1',
  '.sslip.io',
  ...(process.env.VITE_ALLOWED_HOSTS
    ? process.env.VITE_ALLOWED_HOSTS.split(',').map((h) => h.trim()).filter(Boolean)
    : []),
]

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000,
    allowedHosts,
    proxy: {
      '/api': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
      '/oauth': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
      '/.well-known': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
    },
  },
  resolve: {
    alias: {
      '@': '/src',
    },
  },
})
