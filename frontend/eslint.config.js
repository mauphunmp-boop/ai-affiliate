import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'
import reactPlugin from 'eslint-plugin-react'

// Vitest globals (describe,it,expect,vi, beforeEach, etc.) + Node-like process shim for code referencing process
const vitestGlobals = {
  ...globals['jest'], // reuse jest style globals for convenience
  describe: 'readonly', it: 'readonly', test: 'readonly', expect: 'readonly', vi: 'readonly', beforeAll: 'readonly', afterAll: 'readonly', beforeEach: 'readonly', afterEach: 'readonly'
};

// Provide lightweight process polyfill to silence no-undef where code uses process.env.* (Vite substitutes at build)
const processGlobal = { process: 'readonly' };

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{js,jsx}'],
    extends: [
      js.configs.recommended,
      reactHooks.configs['recommended-latest'],
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: { ...globals.browser, ...processGlobal },
      parserOptions: {
        ecmaVersion: 'latest',
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
      },
    },
    plugins: { react: reactPlugin },
    rules: {
      'no-unused-vars': ['error', { varsIgnorePattern: '^[A-Z_]' }],
      'no-empty': ['error', { allowEmptyCatch: true }],
      // Disable noisy rule not critical for build stability
      'react-refresh/only-export-components': 'off',
      // Temporarily suppress until migrated to stricter pattern
      'react/no-did-update-set-state': 'off'
    },
  },
  // Tests & test utilities override
  {
    files: ['src/__tests__/**/*.{js,jsx}', 'src/test/**/*.{js,jsx}', 'src/test/**', 'src/**/test-utils.{js,jsx}'],
    languageOptions: {
      globals: { ...globals.browser, ...vitestGlobals, ...processGlobal }
    },
    rules: {
      'react-refresh/only-export-components': 'off'
    }
  },
])
