import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    allowedHosts: ['host.docker.internal', 'backend'],
    proxy: { '/api': 'http://127.0.0.1:5300' },
  },
})
