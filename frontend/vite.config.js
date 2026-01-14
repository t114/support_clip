import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/upload': 'http://127.0.0.1:8000',
      '/upload-prefix-image': 'http://127.0.0.1:8000',
      '/delete-prefix-image': 'http://127.0.0.1:8000',
      '/burn': 'http://127.0.0.1:8000',
      '/download': 'http://127.0.0.1:8000',
      '/static': 'http://127.0.0.1:8000',
      '/youtube': 'http://127.0.0.1:8000',
      '/progress': 'http://127.0.0.1:8000',
      '/generate-description': 'http://127.0.0.1:8000',
      '/generate-twitter-pr': 'http://127.0.0.1:8000',
      '/hololive-members': 'http://127.0.0.1:8000',
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
