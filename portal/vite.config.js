import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/jobs': 'http://34.30.126.66:8000',
      '/submit': 'http://34.30.126.66:8000',
      '/calendar': 'http://34.30.126.66:8000',
      '/diary': 'http://34.30.126.66:8000',
      '/analytics': 'http://34.30.126.66:8000',
      '/logout': 'http://34.30.126.66:8000',
    }
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  }
})
