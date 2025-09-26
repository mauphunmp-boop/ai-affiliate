import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.js'],
    globals: true,
    coverage: {
      reporter: ['text','lcov'],
      include: ['src/**/*.{js,jsx}'],
      exclude: ['src/test/**','src/**/*.d.ts'],
  thresholds: { lines: 55, statements: 55, branches: 40, functions: 50 }
    }
  }
});
