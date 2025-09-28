import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { visualizer } from 'rollup-plugin-visualizer'

// https://vite.dev/config/
export default defineConfig(() => {
  const enableAnalyze = process.env.ANALYZE === '1';
  return {
    plugins: [
      react(),
      enableAnalyze && visualizer({ filename: 'bundle-report.html', gzipSize: true, brotliSize: true, template: 'treemap', open: false })
    ].filter(Boolean),
    build: {
      sourcemap: enableAnalyze,
    }
  }
})
