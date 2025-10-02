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
    },
    server: {
      host: '0.0.0.0',          // listen on all interfaces so cloudflared can reach it
      port: 5173,
      strictPort: true,
      // Vite v5+ supports allowedHosts (or use allowedHosts plugin in older versions)
      // This authorizes the tunnel-accessed hostname to avoid the blocked request message.
      allowedHosts: ['admin.tuvanmuasam.app'],
      // Optional: if you later add apex chat UI served by a separate Vite instance, extend this list.
    }
  }
})
