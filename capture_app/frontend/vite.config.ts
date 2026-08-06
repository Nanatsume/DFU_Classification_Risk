import path from "node:path"
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      // let `npm run dev` talk to the already-running FastAPI backend, no CORS needed
      '/api': 'http://127.0.0.1:8000',
    },
  },
  build: {
    outDir: '../static',
    emptyOutDir: true,
    rollupOptions: {
      // multi-page app: one real .html file per route, matching the existing URL scheme
      input: {
        index: path.resolve(__dirname, 'index.html'),
        login: path.resolve(__dirname, 'login.html'),
        'crf-form': path.resolve(__dirname, 'crf-form.html'),
        'crf-list': path.resolve(__dirname, 'crf-list.html'),
        'crf-detail': path.resolve(__dirname, 'crf-detail.html'),
        capture: path.resolve(__dirname, 'capture.html'),
      },
    },
  },
})
