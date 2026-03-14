import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8000',
      '/chat': 'http://localhost:8000',
      '/reset': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/session': 'http://localhost:8000',
      '/sessions': 'http://localhost:8000',
      '/voice': 'http://localhost:8000',
      '/benchmark': 'http://localhost:8000',
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
})
