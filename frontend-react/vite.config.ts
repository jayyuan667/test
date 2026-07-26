import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendBase = env.VITE_BACKEND_URL || 'http://127.0.0.1:5190'

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src'),
      },
    },
    server: {
      port: 3200,
      strictPort: true,
      proxy: {
        '/api': {
          target: backendBase,
          changeOrigin: true,
        },
      },
    },
    preview: {
      port: 3201,
      strictPort: true,
    },
  }
})
