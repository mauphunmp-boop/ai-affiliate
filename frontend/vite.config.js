import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { visualizer } from 'rollup-plugin-visualizer'

// https://vite.dev/config/
export default defineConfig(() => {
  const enableAnalyze = process.env.ANALYZE === '1';
  // Allowed hostnames for dev server traffic (defensive guard)
  const allowedHosts = new Set([
    'admin.tuvanmuasam.app',
    'localhost',
    '127.0.0.1',
  ]);

  // Middleware plugin to hard-block unexpected Host headers
  const hostGuard = () => ({
    name: 'host-guard',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        try {
          const host = (req.headers['host'] || '').toString().split(':')[0];
          if (!allowedHosts.has(host)) {
            res.statusCode = 403;
            res.setHeader('Content-Type', 'text/plain; charset=utf-8');
            res.end('Forbidden: host not allowed');
            return;
          }
  } catch {
          // If parsing fails, be safe and deny
          res.statusCode = 403;
          res.setHeader('Content-Type', 'text/plain; charset=utf-8');
          res.end('Forbidden');
          return;
        }
        next();
      });
    },
  });
  return {
    plugins: [
      react(),
      hostGuard(),
      enableAnalyze && visualizer({ filename: 'bundle-report.html', gzipSize: true, brotliSize: true, template: 'treemap', open: false })
    ].filter(Boolean),
    build: {
      sourcemap: enableAnalyze,
      chunkSizeWarningLimit: 900,
      rollupOptions: {
        output: {
          manualChunks(id) {
            // Gom React + MUI + Emotion vào cùng 1 chunk để tránh các vấn đề vòng tham chiếu/TDZ hiếm gặp giữa các chunk riêng biệt
            if (id.includes('node_modules')) {
              if (
                id.includes('react') ||
                id.includes('scheduler') ||
                id.includes('@mui') ||
                id.includes('@emotion')
              ) {
                return 'vendor-ui';
              }
              if (id.includes('xlsx') || id.includes('xlsx-populate') || id.includes('xlsxwriter')) return 'vendor-xlsx';
              if (id.includes('lodash') || id.includes('date-fns') || id.includes('dayjs')) return 'vendor-utils';
              return 'vendor';
            }
          },
        },
      },
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
